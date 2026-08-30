from injection_guard.config import (
    CLASS_INJECTION,
    CLASS_SAFE,
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    PipelineConfig,
)
from injection_guard.policy import decide


class TestDecide:
    def test_low_p1_passes_safe(self):
        dec = decide(p1=0.05, heuristic_flags=[])
        assert dec.assigned_class == CLASS_SAFE
        assert dec.decision == DECISION_PASS
        assert dec.needs_review is False

    def test_high_p1_blocks_injection(self):
        dec = decide(p1=0.90, heuristic_flags=[])
        assert dec.assigned_class == CLASS_INJECTION
        assert dec.decision == DECISION_BLOCK
        assert dec.needs_review is False

    def test_borderline_p1_review_above_half(self):
        dec = decide(p1=0.55, heuristic_flags=[])
        assert dec.assigned_class == CLASS_INJECTION
        assert dec.decision == DECISION_REVIEW
        assert dec.needs_review is True

    def test_borderline_p1_review_below_half(self):
        dec = decide(p1=0.30, heuristic_flags=[])
        assert dec.assigned_class == CLASS_SAFE
        assert dec.decision == DECISION_REVIEW
        assert dec.needs_review is True

    def test_heuristic_override_pass_to_review(self):
        dec = decide(p1=0.02, heuristic_flags=["role_override"])
        assert dec.assigned_class == CLASS_INJECTION
        assert dec.decision == DECISION_REVIEW
        assert dec.needs_review is True

    def test_heuristic_no_override_when_already_blocked(self):
        dec = decide(p1=0.95, heuristic_flags=["obfuscation"])
        assert dec.decision == DECISION_BLOCK
        assert dec.needs_review is False

    def test_custom_thresholds(self):
        cfg = PipelineConfig(t_low=0.30, t_high=0.60)
        dec = decide(p1=0.25, heuristic_flags=[], config=cfg)
        assert dec.decision == DECISION_PASS

    def test_exact_t_low_boundary(self):
        dec = decide(p1=0.15, heuristic_flags=[])
        assert dec.decision == DECISION_REVIEW

    def test_exact_t_high_boundary(self):
        dec = decide(p1=0.75, heuristic_flags=[])
        assert dec.decision == DECISION_BLOCK
