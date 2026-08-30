import json
import re


def extract_json(text: str) -> dict:
    """Extract JSON object from model output, tolerating markdown fences."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    m2 = re.search(r"\{.*\}", text, re.DOTALL)
    if m2:
        return json.loads(m2.group(0))
    return json.loads(text)


VALID_VERDICTS = {"vulnerable", "secure", "uncertain"}


def parse_triage_response(text: str) -> dict:
    """Parse stage-1 response into {"verdict": str, "parse_error": bool}."""
    try:
        obj = extract_json(text)
    except (json.JSONDecodeError, AttributeError):
        return {"verdict": "uncertain", "parse_error": True}

    verdict = str(obj.get("verdict", "")).strip().lower()
    if verdict not in VALID_VERDICTS:
        return {"verdict": "uncertain", "parse_error": True}
    return {"verdict": verdict, "parse_error": False}


def parse_full_analysis_response(text: str) -> dict:
    """Parse stage-2 response into structured dict with parse_error flag."""
    try:
        obj = extract_json(text)
    except (json.JSONDecodeError, AttributeError):
        return {
            "verdict": "uncertain",
            "cwe_id": "",
            "mechanism": "",
            "fixed_code": "",
            "justification": "",
            "parse_error": True,
        }

    verdict = str(obj.get("verdict", "vulnerable")).strip().lower()
    if verdict not in VALID_VERDICTS:
        verdict = "uncertain"

    return {
        "verdict": verdict,
        "cwe_id": str(obj.get("cwe_id", "")).strip(),
        "mechanism": str(obj.get("mechanism", "")).strip(),
        "fixed_code": str(obj.get("fixed_code", "")).strip(),
        "justification": str(obj.get("justification", "")).strip(),
        "parse_error": False,
    }
