import pytest

from injection_guard.classifier import batch_predict, build_classifier
from injection_guard.config import PipelineConfig
from injection_guard.heuristic import detect_heuristic_flags
from injection_guard.policy import decide

SAMPLE_SIZE = 50


@pytest.mark.model
class TestE2EDeterminism:
    def test_repeated_runs_produce_identical_results(self):
        config = PipelineConfig()
        pipe = build_classifier(config)

        from datasets import load_dataset
        ds = load_dataset(config.dataset_id)
        test_texts = ds["test"]["text"][:SAMPLE_SIZE]

        preds_run1 = batch_predict(test_texts, pipe, batch_size=config.batch_size)
        preds_run2 = batch_predict(test_texts, pipe, batch_size=config.batch_size)

        for p1, p2 in zip(preds_run1, preds_run2):
            assert p1.raw_label == p2.raw_label
            assert abs(p1.p1 - p2.p1) < 1e-6

        decisions_run1 = []
        decisions_run2 = []
        for p1, p2 in zip(preds_run1, preds_run2):
            flags1 = detect_heuristic_flags(p1.text)
            flags2 = detect_heuristic_flags(p2.text)
            d1 = decide(p1.p1, flags1, config)
            d2 = decide(p2.p1, flags2, config)
            decisions_run1.append((d1.assigned_class, d1.decision, d1.needs_review))
            decisions_run2.append((d2.assigned_class, d2.decision, d2.needs_review))

        assert decisions_run1 == decisions_run2
