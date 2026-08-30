import json
from pathlib import Path
from unittest.mock import patch

from src.code_review.full_analysis import validate_analysis_result


class TestValidateAnalysisResult:
    def test_parse_error_passes_through(self):
        result = {
            "verdict": "uncertain",
            "cwe_id": "",
            "mechanism": "",
            "fixed_code": "",
            "justification": "",
            "parse_error": True,
        }
        out = validate_analysis_result(result)
        assert out["parse_error"] is True
        assert out["verdict"] == "uncertain"

    def test_valid_cwe_passes(self, tmp_path):
        cwe_dict = tmp_path / "cwe.json"
        cwe_dict.write_text(json.dumps(["CWE-89"]))

        result = {
            "verdict": "vulnerable",
            "cwe_id": "CWE-89",
            "mechanism": "SQL injection",
            "fixed_code": "use params",
            "justification": "safe",
            "parse_error": False,
        }
        with patch("src.code_review.full_analysis.CWE_DICT_PATH", cwe_dict):
            out = validate_analysis_result(result)
        assert out["verdict"] == "vulnerable"
        assert "invalid_cwe_id" not in out

    def test_invalid_cwe_downgrades_to_uncertain(self, tmp_path):
        cwe_dict = tmp_path / "cwe.json"
        cwe_dict.write_text(json.dumps(["CWE-89"]))

        result = {
            "verdict": "vulnerable",
            "cwe_id": "CWE-999999",
            "mechanism": "something",
            "fixed_code": "fix",
            "justification": "because",
            "parse_error": False,
        }
        with patch("src.code_review.full_analysis.CWE_DICT_PATH", cwe_dict):
            out = validate_analysis_result(result)
        assert out["verdict"] == "uncertain"
        assert out["invalid_cwe_id"] is True

    def test_secure_verdict_skips_cwe_check(self, tmp_path):
        cwe_dict = tmp_path / "cwe.json"
        cwe_dict.write_text(json.dumps([]))

        result = {
            "verdict": "secure",
            "cwe_id": "",
            "mechanism": "",
            "fixed_code": "",
            "justification": "",
            "parse_error": False,
        }
        with patch("src.code_review.full_analysis.CWE_DICT_PATH", cwe_dict):
            out = validate_analysis_result(result)
        assert out["verdict"] == "secure"
