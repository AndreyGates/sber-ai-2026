"""Apply replacements to text by character offsets without shifting subsequent spans."""
from __future__ import annotations

from dataclasses import dataclass

from pii.bioes import Entity


@dataclass(frozen=True)
class Replacement:
    entity_id: str
    original: str
    pseudonym: str
    strategy: str


def apply_replacements(
    text: str,
    entities_with_replacements: list[tuple[Entity, str]],
) -> str:
    """Apply replacements to text by character offsets.

    Processes replacements from right to left (highest offset first) so that
    earlier offsets remain valid after later replacements change text length.

    Args:
        text: original text
        entities_with_replacements: list of (entity, replacement_text) pairs

    Returns:
        Text with all replacements applied.
    """
    if not entities_with_replacements:
        return text

    sorted_pairs = sorted(entities_with_replacements, key=lambda p: p[0].start, reverse=True)

    result = text
    for entity, replacement in sorted_pairs:
        result = result[:entity.start] + replacement + result[entity.end:]

    return result
