from injection_guard.config import CLASS_INJECTION, CLASS_SAFE, DECISION_BLOCK, DECISION_PASS, DECISION_REVIEW
from injection_guard.policy import Decision, generate_rationale


class TestRationaleGenerator:
    def test_clean_safe_empty_rationale(self):
        dec = Decision(assigned_class=CLASS_SAFE, decision=DECISION_PASS, needs_review=False)
        assert generate_rationale(p1=0.02, heuristic_flags=[], decision=dec) == ""

    def test_heuristic_flags_listed(self):
        dec = Decision(assigned_class=CLASS_SAFE, decision=DECISION_REVIEW, needs_review=True)
        rationale = generate_rationale(p1=0.05, heuristic_flags=["role_override", "obfuscation"], decision=dec)
        assert "смена роли/инструкций" in rationale
        assert "обфускация" in rationale

    def test_high_confidence_injection_no_heuristic(self):
        dec = Decision(assigned_class=CLASS_INJECTION, decision=DECISION_BLOCK, needs_review=False)
        rationale = generate_rationale(p1=0.92, heuristic_flags=[], decision=dec)
        assert "0.92" in rationale
        assert "injection" in rationale.lower() or "классификатор" in rationale

    def test_borderline_review_rationale(self):
        dec = Decision(assigned_class=CLASS_SAFE, decision=DECISION_REVIEW, needs_review=True)
        rationale = generate_rationale(p1=0.30, heuristic_flags=[], decision=dec)
        assert "пограничн" in rationale or "0.30" in rationale

    def test_heuristic_and_injection_combined(self):
        dec = Decision(assigned_class=CLASS_INJECTION, decision=DECISION_BLOCK, needs_review=False)
        rationale = generate_rationale(p1=0.85, heuristic_flags=["system_prompt_extraction"], decision=dec)
        assert "извлечение системного промпта" in rationale
