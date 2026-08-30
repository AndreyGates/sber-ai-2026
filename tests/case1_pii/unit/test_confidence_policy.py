"""Unit tests for confidence policy (design.md Decision 8, level 1)."""
from pii.bioes import Entity
from pii.config import PipelineConfig
from pii.confidence import PolicyDecision, apply_confidence_policy, filter_entities_by_policy


class TestConfidencePolicy:
    def setup_method(self):
        self.config = PipelineConfig(min_score=0.5, high_confidence_threshold=0.85)

    def test_high_confidence_any_category(self):
        entity = Entity("PERSON_NAME", 0, 10, 0.95)
        decision = apply_confidence_policy(entity, self.config)
        assert decision == PolicyDecision(action="replace", needs_review=False)

    def test_high_confidence_high_risk(self):
        entity = Entity("GOV_ID", 0, 10, 0.90)
        decision = apply_confidence_policy(entity, self.config)
        assert decision == PolicyDecision(action="replace", needs_review=False)

    def test_mid_confidence_high_risk(self):
        entity = Entity("GOV_ID", 0, 10, 0.7)
        decision = apply_confidence_policy(entity, self.config)
        assert decision == PolicyDecision(action="mask", needs_review=True)

    def test_mid_confidence_financial(self):
        entity = Entity("FINANCIAL_ACCOUNT", 0, 10, 0.6)
        decision = apply_confidence_policy(entity, self.config)
        assert decision == PolicyDecision(action="mask", needs_review=True)

    def test_mid_confidence_healthcare(self):
        entity = Entity("HEALTHCARE_DATA", 0, 10, 0.55)
        decision = apply_confidence_policy(entity, self.config)
        assert decision == PolicyDecision(action="mask", needs_review=True)

    def test_mid_confidence_low_risk(self):
        entity = Entity("PERSON_NAME", 0, 10, 0.7)
        decision = apply_confidence_policy(entity, self.config)
        assert decision == PolicyDecision(action="replace", needs_review=False)

    def test_below_min_score(self):
        entity = Entity("PERSON_NAME", 0, 10, 0.3)
        decision = apply_confidence_policy(entity, self.config)
        assert decision == PolicyDecision(action="skip", needs_review=False)

    def test_exact_min_score_boundary(self):
        entity = Entity("PERSON_NAME", 0, 10, 0.5)
        decision = apply_confidence_policy(entity, self.config)
        assert decision.action != "skip"

    def test_exact_high_confidence_boundary(self):
        entity = Entity("GOV_ID", 0, 10, 0.85)
        decision = apply_confidence_policy(entity, self.config)
        assert decision == PolicyDecision(action="replace", needs_review=False)


class TestFilterEntitiesByPolicy:
    def setup_method(self):
        self.config = PipelineConfig(min_score=0.5, high_confidence_threshold=0.85)

    def test_split_accepted_and_skipped(self):
        entities = [
            Entity("PERSON_NAME", 0, 5, 0.9),
            Entity("EMAIL", 10, 20, 0.3),
            Entity("GOV_ID", 25, 35, 0.6),
        ]
        accepted, skipped = filter_entities_by_policy(entities, self.config)
        assert len(accepted) == 2
        assert len(skipped) == 1
        assert skipped[0].label == "EMAIL"

    def test_all_accepted(self):
        entities = [
            Entity("PERSON_NAME", 0, 5, 0.9),
            Entity("EMAIL", 10, 20, 0.95),
        ]
        accepted, skipped = filter_entities_by_policy(entities, self.config)
        assert len(accepted) == 2
        assert len(skipped) == 0

    def test_all_skipped(self):
        entities = [
            Entity("PERSON_NAME", 0, 5, 0.2),
            Entity("EMAIL", 10, 20, 0.1),
        ]
        accepted, skipped = filter_entities_by_policy(entities, self.config)
        assert len(accepted) == 0
        assert len(skipped) == 2
