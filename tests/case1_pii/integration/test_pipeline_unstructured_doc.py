"""Integration test: unstructured document pipeline (requires model)."""
import pytest

from pii.config import PipelineConfig
from pii.pipeline import PIIPipeline


@pytest.mark.model
class TestPipelineUnstructuredDoc:
    @pytest.fixture(autouse=True)
    def setup_pipeline(self):
        self.pipeline = PIIPipeline(PipelineConfig(device="cpu", include_original=True))
        self.pipeline.load_model()

    def test_unstructured_doc_remains_readable(self):
        text = (
            "Dear Mr. Johnson,\n\n"
            "We are writing to confirm your recent visit.\n"
            "Your insurance ID is UHC-9876543.\n"
            "Please call us at (555) 123-4567 if you have questions.\n\n"
            "Best regards,\nDr. Sarah Watson"
        )
        result = self.pipeline.process_document("unstruct-1", text, "letter")
        anon = result["anonymized_text"]
        assert "Dear" in anon
        assert "Best regards" in anon
        assert not _has_double_spaces(anon)

    def test_unstructured_doc_no_raw_pii(self):
        text = "Contact John Smith at john.smith@email.com or (555) 987-6543."
        result = self.pipeline.process_document("unstruct-2", text, "letter")
        assert "john.smith@email.com" not in result["anonymized_text"]


def _has_double_spaces(text: str) -> bool:
    return "  " in text.replace("\n", "").replace("  ", " ")
