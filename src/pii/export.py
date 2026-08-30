"""Export pipeline results to JSON, JSONL, and XLSX formats."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pii.apply import Replacement


DOCUMENT_SCHEMA = {
    "type": "object",
    "required": ["doc_id", "entities", "replacements", "anonymized_text", "metadata"],
    "properties": {
        "doc_id": {"type": "string", "minLength": 1},
        "document_type": {"type": "string"},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["entity_id", "label", "start", "end", "score", "needs_review"],
                "properties": {
                    "entity_id": {"type": "string"},
                    "label": {"type": "string"},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                    "score": {"type": "number"},
                    "needs_review": {"type": "boolean"},
                },
            },
        },
        "replacements": {"type": "object"},
        "anonymized_text": {"type": "string"},
        "metadata": {
            "type": "object",
            "required": ["model", "model_version", "min_score"],
            "properties": {
                "model": {"type": "string"},
                "model_version": {"type": "string"},
                "min_score": {"type": "number"},
                "locale": {"type": "string"},
                "review_required": {"type": "boolean"},
            },
        },
    },
}


def build_document_record(
    doc_id: str,
    entities_json: list[dict],
    replacements: dict[str, dict],
    anonymized_text: str,
    metadata: dict,
    document_type: str = "",
    include_original: bool = False,
) -> dict:
    """Build a single document record in the output contract format."""
    if not include_original:
        sanitized_replacements = {}
        for eid, repl in replacements.items():
            sanitized_replacements[eid] = {
                "original": "",
                "pseudonym": repl.get("pseudonym", ""),
                "strategy": repl.get("strategy", ""),
            }
        replacements = sanitized_replacements

    return {
        "doc_id": doc_id,
        "document_type": document_type,
        "entities": entities_json,
        "replacements": replacements,
        "anonymized_text": anonymized_text,
        "metadata": metadata,
    }


def export_jsonl(records: list[dict], output_path: str | Path) -> None:
    """Write records to a JSONL file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def export_json(records: list[dict], output_path: str | Path) -> None:
    """Write records to a single JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def export_xlsx(records: list[dict], output_path: str | Path) -> None:
    """Write records to an XLSX file with one row per document."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for rec in records:
        rows.append({
            "doc_id": rec["doc_id"],
            "document_type": rec.get("document_type", ""),
            "entities": json.dumps(rec["entities"], ensure_ascii=False),
            "replacements": json.dumps(rec["replacements"], ensure_ascii=False),
            "anonymized_text": rec["anonymized_text"],
            "metadata": json.dumps(rec["metadata"], ensure_ascii=False),
        })

    df = pd.DataFrame(rows)
    df.to_excel(str(path), index=False, engine="openpyxl")


def validate_record(record: dict) -> list[str]:
    """Validate a record against the document schema. Returns list of error messages."""
    errors = []
    for field in DOCUMENT_SCHEMA["required"]:
        if field not in record:
            errors.append(f"Missing required field: {field}")

    if "doc_id" in record and not record["doc_id"]:
        errors.append("doc_id must be non-empty")

    if "entities" in record:
        if not isinstance(record["entities"], list):
            errors.append("entities must be a list")
        else:
            for i, ent in enumerate(record["entities"]):
                for req in ["entity_id", "label", "start", "end", "score", "needs_review"]:
                    if req not in ent:
                        errors.append(f"entities[{i}] missing required field: {req}")

    if "anonymized_text" in record and not isinstance(record["anonymized_text"], str):
        errors.append("anonymized_text must be a string")

    return errors
