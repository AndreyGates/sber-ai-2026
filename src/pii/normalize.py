"""Entity value normalization for consistent deduplication."""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz


WHITESPACE_RE = re.compile(r"\s+")


def normalize_value(value: str) -> str:
    """Normalize an entity value for deduplication: casefold + collapse whitespace."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.casefold()
    normalized = WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def fuzzy_match_names(
    values: list[str],
    threshold: float = 0.8,
) -> dict[str, str]:
    """Cluster similar name strings, returning a mapping from each value to its cluster representative.

    Uses rapidfuzz token_sort_ratio for fuzzy matching.
    """
    if not values:
        return {}

    normalized = {v: normalize_value(v) for v in values}
    clusters: dict[str, str] = {}
    representatives: list[str] = []

    for value in values:
        norm = normalized[value]
        matched_rep = None
        for rep in representatives:
            rep_norm = normalized[rep]
            score = fuzz.token_sort_ratio(norm, rep_norm) / 100.0
            if score >= threshold:
                matched_rep = rep
                break
        if matched_rep is not None:
            clusters[value] = matched_rep
        else:
            representatives.append(value)
            clusters[value] = value

    return clusters
