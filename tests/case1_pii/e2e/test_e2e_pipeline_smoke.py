"""E2E test: pipeline smoke test (no model, uses mocked predictions)."""
import json

import jsonschema

from pii.apply import apply_replacements
from pii.bioes import Entity
from pii.confidence import filter_entities_by_policy
from pii.config import PipelineConfig
from pii.export import build_document_record, validate_record
from pii.regex_fallback import regex_fallback
from pii.registry import PseudonymRegistry
from pii.strategies import get_replacement


def _mock_process_document(doc: dict, config: PipelineConfig) -> dict:
    """Process a document using regex fallback only (no model)."""
    text = doc["text"]
    doc_id = doc["uid"]

    entities = regex_fallback(text, [])
    accepted, _ = filter_entities_by_policy(entities, config)

    registry = PseudonymRegistry(doc_id=doc_id)
    entities_json = []
    replacements = {}
    replacements_for_apply = []

    for idx, (entity, decision) in enumerate(accepted, start=1):
        entity_id = f"e{idx}"
        original_text = text[entity.start:entity.end]
        pseudonym = get_replacement(original_text, entity.label, doc_id, registry, action=decision.action)

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
            "strategy": "regex_fallback",
        }
        replacements_for_apply.append((entity, pseudonym))

    anonymized_text = apply_replacements(text, replacements_for_apply)

    return build_document_record(
        doc_id=doc_id,
        entities_json=entities_json,
        replacements=replacements,
        anonymized_text=anonymized_text,
        metadata={"model": "regex-only", "model_version": "v1", "min_score": config.min_score},
        document_type=doc.get("document_type", ""),
        include_original=config.include_original,
    )


DOCUMENT_SCHEMA = {
    "type": "object",
    "required": ["doc_id", "entities", "replacements", "anonymized_text", "metadata"],
    "properties": {
        "doc_id": {"type": "string", "minLength": 1},
        "entities": {"type": "array"},
        "replacements": {"type": "object"},
        "anonymized_text": {"type": "string"},
        "metadata": {
            "type": "object",
            "required": ["model", "model_version", "min_score"],
        },
    },
}


class TestE2EPipelineSmoke:
    def test_pipeline_runs_without_exceptions(self, fixture_documents, pipeline_config):
        results = []
        for doc in fixture_documents:
            result = _mock_process_document(doc, pipeline_config)
            results.append(result)
        assert len(results) == len(fixture_documents)

    def test_all_records_valid_by_schema(self, fixture_documents, pipeline_config):
        for doc in fixture_documents:
            result = _mock_process_document(doc, pipeline_config)
            jsonschema.validate(result, DOCUMENT_SCHEMA)

    def test_all_records_pass_validation(self, fixture_documents, pipeline_config):
        for doc in fixture_documents:
            result = _mock_process_document(doc, pipeline_config)
            errors = validate_record(result)
            assert errors == [], f"Validation errors for {doc['uid']}: {errors}"

    def test_doc_without_pii_unchanged(self, fixture_documents, pipeline_config):
        no_pii_docs = [d for d in fixture_documents if not d.get("known_pii")]
        for doc in no_pii_docs:
            result = _mock_process_document(doc, pipeline_config)
            assert result["anonymized_text"] == doc["text"]
