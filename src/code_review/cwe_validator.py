import json
import re
from pathlib import Path

_CWE_PATTERN = re.compile(r"^CWE-\d+$")

_dict_cache: set[str] | None = None


def _load_dict(path: Path) -> set[str]:
    global _dict_cache
    if _dict_cache is None:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _dict_cache = set(data)
    return _dict_cache


def reset_cache() -> None:
    global _dict_cache
    _dict_cache = None


def validate_cwe_id(cwe_id: str, dict_path: Path) -> tuple[bool, str]:
    """Validate CWE ID format and presence in dictionary.

    Returns (is_valid, reason) where reason explains invalidity.
    """
    if not cwe_id:
        return False, "empty"
    if not _CWE_PATTERN.match(cwe_id):
        return False, "bad_format"
    known = _load_dict(dict_path)
    if cwe_id not in known:
        return False, "not_in_dict"
    return True, ""
