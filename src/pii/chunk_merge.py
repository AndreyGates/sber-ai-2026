"""Merge entities from overlapping sliding-window chunks."""
from __future__ import annotations

from pii.bioes import Entity


def merge_chunk_entities(
    chunk_entities: list[list[Entity]],
    chunk_char_spans: list[tuple[int, int]],
) -> list[Entity]:
    """Merge entities from overlapping chunks, deduplicating and resolving conflicts.

    For entities that span chunk boundaries:
    - Exact duplicates (same label, start, end): keep max score.
    - Partially overlapping entities of the same label: keep the one with max score.
    - Entities fully within overlap zone: keep max score.

    Args:
        chunk_entities: list of entity lists, one per chunk.
        chunk_char_spans: (char_start, char_end) for each chunk's text coverage.

    Returns:
        Sorted, deduplicated list of entities.
    """
    if not chunk_entities:
        return []

    all_entities: list[Entity] = []
    for entities in chunk_entities:
        all_entities.extend(entities)

    if not all_entities:
        return []

    all_entities.sort(key=lambda e: (e.start, e.end))

    merged: list[Entity] = []
    for entity in all_entities:
        if not merged:
            merged.append(entity)
            continue

        prev = merged[-1]
        if _entities_overlap(prev, entity) and prev.label == entity.label:
            if _is_duplicate(prev, entity):
                if entity.score > prev.score:
                    merged[-1] = entity
            elif _entity_contains(prev, entity):
                pass
            elif _entity_contains(entity, prev):
                merged[-1] = entity
            else:
                if entity.score > prev.score:
                    merged[-1] = entity
        else:
            merged.append(entity)

    return merged


def _entities_overlap(a: Entity, b: Entity) -> bool:
    return a.start < b.end and b.start < a.end


def _is_duplicate(a: Entity, b: Entity) -> bool:
    return a.start == b.start and a.end == b.end


def _entity_contains(outer: Entity, inner: Entity) -> bool:
    return outer.start <= inner.start and outer.end >= inner.end
