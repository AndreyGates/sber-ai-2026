import json
import tempfile
from pathlib import Path

import pytest

from src.code_review.cwe_validator import validate_cwe_id, reset_cache


@pytest.fixture(autouse=True)
def _clear_cache(tmp_path):
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def cwe_dict_path(tmp_path):
    data = ["CWE-89", "CWE-79", "CWE-78", "CWE-22", "CWE-798"]
    path = tmp_path / "cwe_test.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return path


class TestValidateCweId:
    def test_valid_id(self, cwe_dict_path):
        valid, reason = validate_cwe_id("CWE-89", cwe_dict_path)
        assert valid is True
        assert reason == ""

    def test_empty_id(self, cwe_dict_path):
        valid, reason = validate_cwe_id("", cwe_dict_path)
        assert valid is False
        assert reason == "empty"

    def test_bad_format(self, cwe_dict_path):
        valid, reason = validate_cwe_id("CWE89", cwe_dict_path)
        assert valid is False
        assert reason == "bad_format"

    def test_bad_format_letters(self, cwe_dict_path):
        valid, reason = validate_cwe_id("CWE-abc", cwe_dict_path)
        assert valid is False
        assert reason == "bad_format"

    def test_not_in_dict(self, cwe_dict_path):
        valid, reason = validate_cwe_id("CWE-999", cwe_dict_path)
        assert valid is False
        assert reason == "not_in_dict"

    def test_valid_format_not_in_dict(self, cwe_dict_path):
        valid, reason = validate_cwe_id("CWE-100", cwe_dict_path)
        assert valid is False
        assert reason == "not_in_dict"
