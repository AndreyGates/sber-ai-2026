from __future__ import annotations

from dataclasses import dataclass

from .config import (
    CLASS_INJECTION,
    CLASS_SAFE,
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    PipelineConfig,
)
from .heuristic import CATEGORY_LABELS


@dataclass
class Decision:
    assigned_class: str
    decision: str
    needs_review: bool


def decide(
    p1: float,
    heuristic_flags: list[str],
    config: PipelineConfig | None = None,
) -> Decision:
    if config is None:
        config = PipelineConfig()

    if p1 < config.t_low:
        assigned_class = CLASS_SAFE
        decision = DECISION_PASS
        needs_review = False
    elif p1 >= config.t_high:
        assigned_class = CLASS_INJECTION
        decision = DECISION_BLOCK
        needs_review = False
    else:
        assigned_class = CLASS_INJECTION if p1 >= 0.5 else CLASS_SAFE
        decision = DECISION_REVIEW
        needs_review = True

    if heuristic_flags and decision == DECISION_PASS:
        assigned_class = CLASS_INJECTION
        decision = DECISION_REVIEW
        needs_review = True

    return Decision(
        assigned_class=assigned_class,
        decision=decision,
        needs_review=needs_review,
    )


def generate_rationale(
    p1: float,
    heuristic_flags: list[str],
    decision: Decision,
) -> str:
    if not heuristic_flags and decision.assigned_class == CLASS_SAFE and not decision.needs_review:
        return ""

    parts: list[str] = []

    if heuristic_flags:
        flag_labels = [CATEGORY_LABELS.get(f, f) for f in heuristic_flags]
        parts.append("обнаружены признаки: " + ", ".join(flag_labels))

    if decision.assigned_class == CLASS_INJECTION and not heuristic_flags:
        parts.append(f"классификатор оценил запрос как injection with confidence {p1:.2f}")
    elif decision.needs_review and not heuristic_flags:
        parts.append(f"пограничная уверенность классификатора (p={p1:.2f})")

    return "; ".join(parts)
