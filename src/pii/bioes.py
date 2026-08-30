"""BIOES tag sequence → span-level entities decoder."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entity:
    label: str
    start: int
    end: int
    score: float

    @property
    def text_hint(self) -> str:
        return f"<{self.label} @{self.start}:{self.end}>"


def _split_tag(tag: str) -> tuple[str, str]:
    """Split 'B-PERSON_NAME' → ('B', 'PERSON_NAME'). 'O' → ('O', '')."""
    if tag == "O" or tag.startswith("O-"):
        return "O", ""
    parts = tag.split("-", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "O", ""


def bioes_decode(
    tags: list[str],
    char_offsets: list[tuple[int, int]],
    scores: list[float],
) -> list[Entity]:
    """Decode a BIOES tag sequence into span-level entities.

    Args:
        tags: BIOES tag per token (e.g. ["B-PERSON", "E-PERSON", "O", ...]).
        char_offsets: (start, end) character offsets per token in the original text.
        scores: confidence score per token.

    Returns:
        List of Entity with character-level start/end in the original text.
    """
    if not tags:
        return []

    entities: list[Entity] = []
    i = 0
    n = len(tags)

    while i < n:
        prefix, label = _split_tag(tags[i])

        if prefix == "S":
            start, end = char_offsets[i]
            entities.append(Entity(label=label, start=start, end=end, score=scores[i]))
            i += 1
            continue

        if prefix == "B":
            span_start = char_offsets[i][0]
            span_scores = [scores[i]]
            j = i + 1
            found_e = False
            while j < n:
                p2, l2 = _split_tag(tags[j])
                if p2 == "I" and l2 == label:
                    span_scores.append(scores[j])
                    j += 1
                elif p2 == "E" and l2 == label:
                    span_scores.append(scores[j])
                    span_end = char_offsets[j][1]
                    avg_score = sum(span_scores) / len(span_scores)
                    entities.append(Entity(label=label, start=span_start, end=span_end, score=avg_score))
                    i = j + 1
                    found_e = True
                    break
                else:
                    break
            if not found_e:
                i += 1
            continue

        i += 1

    return entities


def merge_entity_lists(*lists: list[Entity]) -> list[Entity]:
    """Merge multiple entity lists, deduplicating by (start, end, label), keeping max score."""
    seen: dict[tuple[str, int, int], Entity] = {}
    for entities in lists:
        for e in entities:
            key = (e.label, e.start, e.end)
            if key not in seen or e.score > seen[key].score:
                seen[key] = e
    return sorted(seen.values(), key=lambda e: e.start)
