"""Integration tests for export: final vs audit artifacts."""
import json

from pii.export import build_document_record, export_json, export_jsonl, export_xlsx, validate_record


def _make_sample_record(include_original: bool) -> dict:
    return build_document_record(
        doc_id="test-doc-1",
        entities_json=[
            {"entity_id": "e1", "label": "PERSON_NAME", "start": 0, "end": 11, "score": 0.95, "needs_review": False},
        ],
        replacements={
            "e1": {"original": "John Smith", "pseudonym": "Alex Brown", "strategy": "consistent_pseudonym"},
        },
        anonymized_text="Alex Brown went to the store.",
        metadata={"model": "test-model", "model_version": "v1", "min_score": 0.5},
        include_original=include_original,
    )


class TestExportFinalVsAudit:
    def test_audit_contains_original(self, tmp_path):
        record = _make_sample_record(include_original=True)
        assert record["replacements"]["e1"]["original"] == "John Smith"

    def test_final_hides_original(self, tmp_path):
        record = _make_sample_record(include_original=False)
        assert record["replacements"]["e1"]["original"] == ""

    def test_final_does_not_contain_pii_substrings(self, tmp_path):
        record = _make_sample_record(include_original=False)
        serialized = json.dumps(record, ensure_ascii=False)
        assert "John Smith" not in serialized

    def test_audit_contains_pii_substrings(self, tmp_path):
        record = _make_sample_record(include_original=True)
        serialized = json.dumps(record, ensure_ascii=False)
        assert "John Smith" in serialized

    def test_jsonl_export(self, tmp_path):
        records = [_make_sample_record(include_original=False)]
        path = tmp_path / "output.jsonl"
        export_jsonl(records, path)
        assert path.exists()
        with path.open() as f:
            loaded = json.loads(f.readline())
        assert loaded["doc_id"] == "test-doc-1"

    def test_json_export(self, tmp_path):
        records = [_make_sample_record(include_original=False)]
        path = tmp_path / "output.json"
        export_json(records, path)
        assert path.exists()
        with path.open() as f:
            loaded = json.load(f)
        assert len(loaded) == 1

    def test_xlsx_export(self, tmp_path):
        records = [_make_sample_record(include_original=False)]
        path = tmp_path / "output.xlsx"
        export_xlsx(records, path)
        assert path.exists()

        import pandas as pd
        df = pd.read_excel(str(path), engine="openpyxl")
        assert len(df) == 1
        assert "doc_id" in df.columns
        assert "anonymized_text" in df.columns
        assert "entities" in df.columns
        assert "replacements" in df.columns

    def test_xlsx_no_pii_leak(self, tmp_path):
        records = [_make_sample_record(include_original=False)]
        path = tmp_path / "output.xlsx"
        export_xlsx(records, path)

        import pandas as pd
        df = pd.read_excel(str(path), engine="openpyxl")
        for col in df.columns:
            for val in df[col].fillna("").astype(str):
                assert "John Smith" not in str(val)


class TestValidation:
    def test_valid_record(self):
        record = _make_sample_record(include_original=False)
        errors = validate_record(record)
        assert errors == []

    def test_missing_doc_id(self):
        record = {"entities": [], "replacements": {}, "anonymized_text": "", "metadata": {}}
        errors = validate_record(record)
        assert any("doc_id" in e for e in errors)

    def test_empty_doc_id(self):
        record = _make_sample_record(include_original=False)
        record["doc_id"] = ""
        errors = validate_record(record)
        assert any("non-empty" in e for e in errors)

    def test_missing_entities_field(self):
        record = {"doc_id": "x", "replacements": {}, "anonymized_text": "", "metadata": {}}
        errors = validate_record(record)
        assert any("entities" in e for e in errors)

    def test_entity_missing_required_fields(self):
        record = _make_sample_record(include_original=False)
        record["entities"] = [{"entity_id": "e1"}]
        errors = validate_record(record)
        assert len(errors) > 0
