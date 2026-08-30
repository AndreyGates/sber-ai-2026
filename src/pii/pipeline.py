"""Main PII anonymization pipeline orchestrator."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

from pii.apply import Replacement, apply_replacements
from pii.bioes import Entity, bioes_decode
from pii.chunk_merge import merge_chunk_entities
from pii.config import PipelineConfig
from pii.confidence import PolicyDecision, filter_entities_by_policy
from pii.export import build_document_record
from pii.normalize import fuzzy_match_names, normalize_value
from pii.regex_fallback import regex_fallback
from pii.registry import PseudonymRegistry
from pii.strategies import get_replacement
from pii.tokenizer import WindowChunk, create_windows

logger = logging.getLogger(__name__)


class PIIPipeline:
    """Batch PII anonymization pipeline."""

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()
        self._tokenizer = None
        self._model = None
        self._id2label: dict[int, str] = {}

    def load_model(self) -> None:
        """Load model and tokenizer."""
        logger.info("Loading model %s (revision=%s)", self.config.model_name, self.config.model_revision)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            revision=self.config.model_revision,
        )
        self._model = AutoModelForTokenClassification.from_pretrained(
            self.config.model_name,
            revision=self.config.model_revision,
        )
        self._id2label = self._model.config.id2label

        device = self.config.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device = torch.device(device)
        self._model.to(self._device)

        dtype_map = {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }
        self._dtype = dtype_map.get(self.config.dtype, torch.float32)
        self._model.eval()

        logger.info("Model loaded on %s with dtype=%s", self._device, self.config.dtype)

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    def process_document(self, doc_id: str, text: str, document_type: str = "", locale: str = "ru") -> dict:
        """Process a single document through the full pipeline."""
        if not self.model_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        chunks = create_windows(
            text,
            self._tokenizer,
            max_length=self.config.max_length,
            overlap=self.config.overlap,
        )

        chunk_entity_lists: list[list[Entity]] = []
        chunk_char_spans: list[tuple[int, int]] = []

        for i in range(0, len(chunks), self.config.batch_size):
            batch_chunks = chunks[i:i + self.config.batch_size]
            batch_entities = self._infer_batch(text, batch_chunks)
            chunk_entity_lists.extend(batch_entities)
            chunk_char_spans.extend([(c.char_start, c.char_end) for c in batch_chunks])

        entities = merge_chunk_entities(chunk_entity_lists, chunk_char_spans)

        regex_entities = regex_fallback(text, entities)
        all_entities = entities + regex_entities
        all_entities.sort(key=lambda e: e.start)

        accepted, _skipped = filter_entities_by_policy(all_entities, self.config)

        registry = PseudonymRegistry(doc_id=doc_id, locale=locale)
        entities_json: list[dict] = []
        replacements: dict[str, dict] = {}
        replacements_for_apply: list[tuple[Entity, str]] = []

        for idx, (entity, decision) in enumerate(accepted, start=1):
            entity_id = f"e{idx}"
            original_text = text[entity.start:entity.end]
            pseudonym = get_replacement(
                original_text,
                entity.label,
                doc_id,
                registry,
                action=decision.action,
            )

            entities_json.append({
                "entity_id": entity_id,
                "label": entity.label,
                "start": entity.start,
                "end": entity.end,
                "score": round(entity.score, 4),
                "needs_review": decision.needs_review,
            })

            replacements[entity_id] = {
                "original": original_text,
                "pseudonym": pseudonym,
                "strategy": _strategy_name(entity.label, decision),
            }

            replacements_for_apply.append((entity, pseudonym))

        anonymized_text = apply_replacements(text, replacements_for_apply)

        any_review = any(d.needs_review for _, d in accepted)

        metadata = {
            "model": self.config.model_name,
            "model_version": self.config.model_revision,
            "min_score": self.config.min_score,
            "locale": locale,
            "review_required": any_review,
        }

        return build_document_record(
            doc_id=doc_id,
            entities_json=entities_json,
            replacements=replacements,
            anonymized_text=anonymized_text,
            metadata=metadata,
            document_type=document_type,
            include_original=self.config.include_original,
        )

    def process_batch(
        self,
        documents: list[dict],
    ) -> list[dict]:
        """Process a batch of documents.

        Args:
            documents: list of dicts with 'uid'/'doc_id', 'text', and optionally 'document_type'.
        """
        results = []
        for i, doc in enumerate(documents):
            doc_id = doc.get("uid") or doc.get("doc_id") or f"doc_{i}"
            text = doc["text"]
            document_type = doc.get("document_type", "")
            locale = doc.get("locale", "ru")

            logger.info("Processing document %d/%d: %s", i + 1, len(documents), doc_id)
            try:
                result = self.process_document(doc_id, text, document_type, locale=locale)
                results.append(result)
            except Exception:
                logger.exception("Failed to process document %s", doc_id)
                results.append(build_document_record(
                    doc_id=doc_id,
                    entities_json=[],
                    replacements={},
                    anonymized_text=text,
                    metadata={
                        "model": self.config.model_name,
                        "model_version": self.config.model_revision,
                        "min_score": self.config.min_score,
                        "locale": locale,
                        "error": True,
                    },
                    document_type=document_type,
                    include_original=self.config.include_original,
                ))

        return results

    def _infer_batch(
        self,
        text: str,
        chunks: list[WindowChunk],
    ) -> list[list[Entity]]:
        """Run model inference on a batch of chunks."""
        results: list[list[Entity]] = []

        for chunk in chunks:
            input_ids = torch.tensor([chunk.token_ids]).to(self._device)

            with torch.no_grad():
                outputs = self._model(input_ids)

            logits = outputs.logits[0]
            probs = torch.softmax(logits, dim=-1)
            pred_ids = torch.argmax(probs, dim=-1)

            tags: list[str] = []
            scores: list[float] = []
            char_offsets: list[tuple[int, int]] = []

            encoding = self._tokenizer(
                text[chunk.char_start:chunk.char_end],
                return_offsets_mapping=True,
                add_special_tokens=True,
                truncation=True,
                max_length=self.config.max_length,
            )
            offset_mapping = encoding["offset_mapping"]

            for tok_idx in range(len(pred_ids)):
                tag = self._id2label.get(pred_ids[tok_idx].item(), "O")
                tags.append(tag)
                scores.append(probs[tok_idx][pred_ids[tok_idx]].item())

                if tok_idx < len(offset_mapping):
                    os, oe = offset_mapping[tok_idx]
                    char_offsets.append((chunk.char_start + os, chunk.char_start + oe))
                else:
                    char_offsets.append((chunk.char_end, chunk.char_end))

            entities = bioes_decode(tags, char_offsets, scores)
            results.append(entities)

        return results


def _strategy_name(label: str, decision: PolicyDecision) -> str:
    if decision.action == "mask":
        return "partial_mask"
    if label in ("PERSON_NAME", "PERSON", "NAME"):
        return "consistent_pseudonym"
    if label in ("PHONE_NUMBER", "PHONE", "CARD_NUMBER", "GOV_ID", "DOCUMENT_NUMBER"):
        return "format_preserving_mask"
    if label in ("EMAIL",):
        return "email_mask"
    if label in ("DATE_OF_BIRTH", "DATE"):
        return "date_generalization"
    if label in ("ADDRESS",):
        return "address_generalization"
    if label in ("HEALTHCARE_DATA", "MEDICAL_RECORD"):
        return "category_label"
    return "pseudonym"
