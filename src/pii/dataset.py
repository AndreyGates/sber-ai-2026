"""Dataset loading utilities for nvidia/Nemotron-PII."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_nemotron_pii(
    split: str = "test",
    max_samples: int | None = None,
    stratify_by: str | None = None,
    cache_dir: str | None = None,
) -> list[dict]:
    """Load the nvidia/Nemotron-PII dataset.

    Args:
        split: dataset split ('test', 'train', etc.)
        max_samples: limit number of samples (None = all)
        stratify_by: if set, sample evenly across values of this field
        cache_dir: HF cache directory

    Returns:
        List of document dicts with keys: uid, text, document_type, document_format,
        domain, locale, spans, etc.
    """
    from datasets import load_dataset

    logger.info("Loading nvidia/Nemotron-PII split=%s", split)
    ds = load_dataset("nvidia/Nemotron-PII", split=split, cache_dir=cache_dir)

    records = [dict(row) for row in ds]

    if stratify_by and max_samples:
        records = _stratified_sample(records, stratify_by, max_samples)
    elif max_samples:
        records = records[:max_samples]

    logger.info("Loaded %d documents", len(records))
    return records


def _stratified_sample(records: list[dict], field: str, n: int) -> list[dict]:
    """Sample n records stratified by the given field."""
    from collections import defaultdict

    groups: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        key = rec.get(field, "unknown")
        groups[key].append(rec)

    per_group = max(1, n // len(groups))
    result: list[dict] = []
    for group_records in groups.values():
        result.extend(group_records[:per_group])

    if len(result) > n:
        result = result[:n]

    return result


def load_from_jsonl(path: str | Path) -> list[dict]:
    """Load documents from a JSONL file."""
    records = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_jsonl(records: list[dict], path: str | Path) -> None:
    """Save records to a JSONL file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
