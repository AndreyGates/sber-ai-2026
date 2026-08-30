import json
from pathlib import Path

import pandas as pd

from src.code_review.export import merge_and_export, validate_output


class TestMergeAndExport:
    def test_merge_secure_only(self, tmp_path):
        stage1 = tmp_path / "s1.jsonl"
        stage2 = tmp_path / "s2.jsonl"

        stage1.write_text(json.dumps({"unique_id": 1, "verdict": "secure", "parse_error": False}) + "\n")
        stage2.write_text("")

        dataset = [{"unique_id": 1, "code": "print('hello')"}]
        out_dir = tmp_path / "out"

        df = merge_and_export(stage1, stage2, dataset, out_dir)
        assert len(df) == 1
        assert df.iloc[0]["verdict"] == "secure"
        assert df.iloc[0]["cwe_id"] == ""
        assert (out_dir / "case3_results.xlsx").exists()
        assert (out_dir / "case3_results.csv").exists()

    def test_merge_vulnerable_with_analysis(self, tmp_path):
        stage1 = tmp_path / "s1.jsonl"
        stage2 = tmp_path / "s2.jsonl"

        stage1.write_text(json.dumps({"unique_id": 1, "verdict": "vulnerable", "parse_error": False}) + "\n")
        stage2.write_text(
            json.dumps({
                "unique_id": 1,
                "verdict": "vulnerable",
                "cwe_id": "CWE-89",
                "mechanism": "SQL injection",
                "fixed_code": "use params",
                "justification": "parameterized query",
            }) + "\n"
        )

        dataset = [{"unique_id": 1, "code": "sql = 'SELECT * FROM ' + input"}]
        out_dir = tmp_path / "out"

        df = merge_and_export(stage1, stage2, dataset, out_dir)
        assert len(df) == 1
        assert df.iloc[0]["verdict"] == "vulnerable"
        assert df.iloc[0]["cwe_id"] == "CWE-89"
        assert df.iloc[0]["fixed_code"] == "use params"


class TestValidateOutput:
    def test_valid_output(self):
        df = pd.DataFrame([{
            "unique_id": 1,
            "code": "x",
            "verdict": "vulnerable",
            "cwe_id": "CWE-89",
            "mechanism": "sqli",
            "fixed_code": "fix",
            "justification": "safe",
        }])
        errors = validate_output(df)
        assert errors == []

    def test_empty_verdict_error(self):
        df = pd.DataFrame([{
            "unique_id": 1,
            "code": "x",
            "verdict": None,
            "cwe_id": "",
            "mechanism": "",
            "fixed_code": "",
            "justification": "",
        }])
        errors = validate_output(df)
        assert any("empty verdict" in e for e in errors)

    def test_vulnerable_without_cwe_error(self):
        df = pd.DataFrame([{
            "unique_id": 1,
            "code": "x",
            "verdict": "vulnerable",
            "cwe_id": "",
            "mechanism": "",
            "fixed_code": "fix",
            "justification": "",
        }])
        errors = validate_output(df)
        assert any("empty CWE" in e for e in errors)
