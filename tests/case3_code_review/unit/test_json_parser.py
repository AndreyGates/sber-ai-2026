from src.code_review.json_parser import (
    extract_json,
    parse_triage_response,
    parse_full_analysis_response,
)


class TestExtractJson:
    def test_plain_json(self):
        assert extract_json('{"verdict": "secure"}') == {"verdict": "secure"}

    def test_json_in_markdown_fence(self):
        text = '```json\n{"verdict": "vulnerable"}\n```'
        assert extract_json(text) == {"verdict": "vulnerable"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"verdict": "uncertain"} and more text'
        assert extract_json(text) == {"verdict": "uncertain"}

    def test_invalid_json_raises(self):
        import pytest
        with pytest.raises(Exception):
            extract_json("not json at all")


class TestParseTriageResponse:
    def test_valid_secure(self):
        result = parse_triage_response('{"verdict": "secure"}')
        assert result == {"verdict": "secure", "parse_error": False}

    def test_valid_vulnerable(self):
        result = parse_triage_response('{"verdict": "vulnerable"}')
        assert result == {"verdict": "vulnerable", "parse_error": False}

    def test_valid_uncertain(self):
        result = parse_triage_response('{"verdict": "uncertain"}')
        assert result == {"verdict": "uncertain", "parse_error": False}

    def test_invalid_verdict_degrades_to_uncertain(self):
        result = parse_triage_response('{"verdict": "maybe"}')
        assert result == {"verdict": "uncertain", "parse_error": True}

    def test_invalid_json_degrades_to_uncertain(self):
        result = parse_triage_response("not json")
        assert result == {"verdict": "uncertain", "parse_error": True}

    def test_empty_verdict_degrades(self):
        result = parse_triage_response('{"verdict": ""}')
        assert result == {"verdict": "uncertain", "parse_error": True}

    def test_case_insensitive(self):
        result = parse_triage_response('{"verdict": "SECURE"}')
        assert result == {"verdict": "secure", "parse_error": False}


class TestParseFullAnalysisResponse:
    def test_valid_vulnerable(self):
        text = '{"verdict": "vulnerable", "cwe_id": "CWE-89", "mechanism": "SQL injection", "fixed_code": "use params", "justification": "parameterized"}'
        result = parse_full_analysis_response(text)
        assert result["verdict"] == "vulnerable"
        assert result["cwe_id"] == "CWE-89"
        assert result["parse_error"] is False

    def test_invalid_json_degrades(self):
        result = parse_full_analysis_response("garbage")
        assert result["verdict"] == "uncertain"
        assert result["parse_error"] is True
        assert result["cwe_id"] == ""

    def test_missing_fields_default_empty(self):
        text = '{"verdict": "vulnerable"}'
        result = parse_full_analysis_response(text)
        assert result["verdict"] == "vulnerable"
        assert result["cwe_id"] == ""
        assert result["mechanism"] == ""
        assert result["fixed_code"] == ""
        assert result["justification"] == ""
