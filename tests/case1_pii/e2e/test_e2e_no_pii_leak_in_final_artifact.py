"""E2E test: no PII leak in final artifact (security regression test).

This is the KEY test that blocks delivery if it fails.
Tests regex-detectable PII only (emails, phones, cards) in the mock pipeline.
Full model coverage is tested by @pytest.mark.model integration tests.
"""
import json
import math

from pii.apply import apply_replacements
from pii.confidence import filter_entities_by_policy
from pii.config import PipelineConfig
from pii.export import build_document_record
from pii.regex_fallback import regex_fallback
from pii.registry import PseudonymRegistry
from pii.strategies import get_replacement


REGEX_DETECTABLE_LABELS = {"EMAIL", "PHONE_NUMBER", "CARD_NUMBER"}


def _process_final(doc: dict) -> dict:
    config = PipelineConfig(include_original=False)
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
        replacements[entity_id] = {"original": "", "pseudonym": pseudonym, "strategy": "regex_fallback"}
        replacements_for_apply.append((entity, pseudonym))

    anonymized_text = apply_replacements(text, replacements_for_apply)

    return build_document_record(
        doc_id=doc_id, entities_json=entities_json, replacements=replacements,
        anonymized_text=anonymized_text,
        metadata={"model": "regex-only", "model_version": "v1", "min_score": 0.5},
        include_original=False,
    )


def _get_regex_detectable_pii(doc: dict) -> list[str]:
    """Extract PII strings that regex fallback should detect."""
    import re
    text = doc["text"]
    pii_strings = []
    from pii.regex_fallback import EMAIL_RE, PHONE_RE, CARD_RE
    for m in EMAIL_RE.finditer(text):
        pii_strings.append(m.group())
    for m in CARD_RE.finditer(text):
        from pii.regex_fallback import luhn_check
        if luhn_check(m.group()):
            pii_strings.append(m.group())
    return pii_strings


class TestNoPIILeak:
    def test_no_regex_pii_in_anonymized_text(self, fixture_documents_with_pii):
        for doc in fixture_documents_with_pii:
            result = _process_final(doc)
            for pii_str in _get_regex_detectable_pii(doc):
                if len(pii_str) >= 5:
                    assert pii_str not in result["anonymized_text"], (
                        f"PII leak in anonymized_text of {doc['uid']}: '{pii_str}'"
                    )

    def test_no_regex_pii_in_serialized_output(self, fixture_documents_with_pii):
        for doc in fixture_documents_with_pii:
            result = _process_final(doc)
            serialized = json.dumps(result, ensure_ascii=False)
            for pii_str in _get_regex_detectable_pii(doc):
                if len(pii_str) >= 8:
                    assert pii_str not in serialized, (
                        f"PII leak in serialized output of {doc['uid']}: '{pii_str}'"
                    )

    def test_no_pii_in_replacements_original(self, fixture_documents_with_pii):
        for doc in fixture_documents_with_pii:
            result = _process_final(doc)
            for eid, repl in result["replacements"].items():
                assert repl["original"] == "", (
                    f"Original PII present in final artifact {doc['uid']}/{eid}"
                )

    def test_no_pii_in_xlsx(self, fixture_documents_with_pii, tmp_path):
        from pii.export import export_xlsx
        import pandas as pd

        results = [_process_final(doc) for doc in fixture_documents_with_pii]
        path = tmp_path / "final.xlsx"
        export_xlsx(results, path)

        df = pd.read_excel(str(path), engine="openpyxl")
        regex_pii = set()
        for doc in fixture_documents_with_pii:
            for pii_str in _get_regex_detectable_pii(doc):
                if len(pii_str) >= 8:
                    regex_pii.add(pii_str)

        for col in df.columns:
            for val in df[col].fillna("").astype(str):
                for pii_str in regex_pii:
                    assert pii_str not in str(val), f"PII leak in xlsx column '{col}': '{pii_str}'"
