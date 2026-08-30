"""Confidence policy: decide action and needs_review flag per entity."""
from __future__ import annotations

from dataclasses import dataclass

from pii.bioes import Entity
from pii.config import PipelineConfig


@dataclass(frozen=True)
class PolicyDecision:
    action: str  # "replace", "mask", "skip"
    needs_review: bool


def apply_confidence_policy(
    entity: Entity,
    config: PipelineConfig,
) -> PolicyDecision:
    """Apply the confidence policy to an entity.

    Rules (from design.md Decision 3):
    - score >= high_confidence_threshold → replace, needs_review=False
    - min_score <= score < high_confidence_threshold AND high-risk category → mask, needs_review=True
    - min_score <= score < high_confidence_threshold AND not high-risk → replace, needs_review=False
    - score < min_score → skip (but regex fallback may still catch it)
    """
    if entity.score >= config.high_confidence_threshold:
        return PolicyDecision(action="replace", needs_review=False)

    if entity.score >= config.min_score:
        if entity.label in config.high_risk_categories:
            return PolicyDecision(action="mask", needs_review=True)
        return PolicyDecision(action="replace", needs_review=False)

    return PolicyDecision(action="skip", needs_review=False)


def filter_entities_by_policy(
    entities: list[Entity],
    config: PipelineConfig,
) -> tuple[list[tuple[Entity, PolicyDecision]], list[Entity]]:
    """Split entities into (accepted with decision, skipped).

    Returns:
        Tuple of:
        - list of (entity, decision) pairs for entities that pass the policy
        - list of entities that were skipped (below min_score)
    """
    accepted: list[tuple[Entity, PolicyDecision]] = []
    skipped: list[Entity] = []

    for entity in entities:
        decision = apply_confidence_policy(entity, config)
        if decision.action == "skip":
            skipped.append(entity)
        else:
            accepted.append((entity, decision))

    return accepted, skipped
