"""Regex fallback layer for high-structure PII patterns (defense-in-depth)."""
from __future__ import annotations

import re

from pii.bioes import Entity

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s.\-]?)?\(?\d{2,4}\)?[\s.\-]?\d{2,4}[\s.\-]?\d{2,4}[\s.\-]?\d{0,4}",
)

CARD_RE = re.compile(
    r"\b(?:\d[ \-]?){12,18}\d\b",
)

ACCOUNT_RE = re.compile(
    r"\b\d{8,20}\b",
)


def luhn_check(number: str) -> bool:
    """Validate a number string using the Luhn algorithm."""
    digits = re.sub(r"\D", "", number)
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def regex_fallback(text: str, existing_entities: list[Entity]) -> list[Entity]:
    """Find PII patterns via regex that the model may have missed.

    Returns entities only for patterns not already covered by existing entities.
    """
    covered = _build_covered_set(existing_entities)
    found: list[Entity] = []

    for m in EMAIL_RE.finditer(text):
        span = (m.start(), m.end())
        if not _is_covered(span, covered):
            found.append(Entity(
                label="EMAIL",
                start=m.start(),
                end=m.end(),
                score=0.6,
            ))

    for m in PHONE_RE.finditer(text):
        span = (m.start(), m.end())
        digits_only = re.sub(r"\D", "", m.group())
        if 7 <= len(digits_only) <= 15 and not _is_covered(span, covered):
            found.append(Entity(
                label="PHONE_NUMBER",
                start=m.start(),
                end=m.end(),
                score=0.55,
            ))

    for m in CARD_RE.finditer(text):
        span = (m.start(), m.end())
        if luhn_check(m.group()) and not _is_covered(span, covered):
            found.append(Entity(
                label="CARD_NUMBER",
                start=m.start(),
                end=m.end(),
                score=0.7,
            ))

    return found


def _build_covered_set(entities: list[Entity]) -> list[tuple[int, int]]:
    return [(e.start, e.end) for e in entities]


def _is_covered(span: tuple[int, int], covered: list[tuple[int, int]]) -> bool:
    s, e = span
    for cs, ce in covered:
        if s >= cs and e <= ce:
            return True
    return False
