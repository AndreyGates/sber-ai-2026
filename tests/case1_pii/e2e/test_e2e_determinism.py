"""E2E test: determinism — two runs produce identical results."""
import json

from pii.apply import apply_replacements
from pii.confidence import filter_entities_by_policy
from pii.config import PipelineConfig
from pii.export import build_document_record
from pii.regex_fallback import regex_fallback
from pii.registry import PseudonymRegistry
from pii.strategies import get_replacement


def _process(doc: dict, config: PipelineConfig) -> dict:
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
            "entity_id": entity_id, "label": entity.label,
            "start": entity.start, "end": entity.end,
            "score": round(entity.score, 4), "needs_review": decision.needs_review,
        })
        replacements[entity_id] = {"original": original_text, "pseudonym": pseudonym, "strategy": "test"}
        replacements_for_apply.append((entity, pseudonym))

    anonymized_text = apply_replacements(text, replacements_for_apply)

    return build_document_record(
        doc_id=doc_id, entities_json=entities_json, replacements=replacements,
        anonymized_text=anonymized_text,
        metadata={"model": "test", "model_version": "v1", "min_score": 0.5},
        include_original=True,
    )


class TestDeterminism:
    def test_two_runs_identical_anonymized_text(self, fixture_documents):
        config = PipelineConfig(include_original=True)
        run1 = [_process(doc, config) for doc in fixture_documents]
        run2 = [_process(doc, config) for doc in fixture_documents]

        for r1, r2 in zip(run1, run2):
            assert r1["anonymized_text"] == r2["anonymized_text"]

    def test_two_runs_identical_replacements(self, fixture_documents):
        config = PipelineConfig(include_original=True)
        run1 = [_process(doc, config) for doc in fixture_documents]
        run2 = [_process(doc, config) for doc in fixture_documents]

        for r1, r2 in zip(run1, run2):
            assert json.dumps(r1["replacements"], sort_keys=True) == json.dumps(
                r2["replacements"], sort_keys=True,
            )

    def test_two_runs_identical_entities(self, fixture_documents):
        config = PipelineConfig(include_original=True)
        run1 = [_process(doc, config) for doc in fixture_documents]
        run2 = [_process(doc, config) for doc in fixture_documents]

        for r1, r2 in zip(run1, run2):
            assert json.dumps(r1["entities"]) == json.dumps(r2["entities"])
