"""Integration test: structured document pipeline (requires model)."""
import pytest

from pii.config import PipelineConfig
from pii.pipeline import PIIPipeline


@pytest.mark.model
class TestPipelineStructuredDoc:
    @pytest.fixture(autouse=True)
    def setup_pipeline(self):
        self.pipeline = PIIPipeline(PipelineConfig(device="cpu", include_original=True))
        self.pipeline.load_model()

    def test_structured_doc_preserves_field_labels(self):
        text = (
            "ФИО: Иванов Пётр Сергеевич\n"
            "Телефон: +7 (912) 345-67-89\n"
            "Email: ivan.petrov@bank.ru\n"
        )
        result = self.pipeline.process_document("struct-1", text, "application_form")
        assert "ФИО:" in result["anonymized_text"]
        assert "Телефон:" in result["anonymized_text"]
        assert "Email:" in result["anonymized_text"]

    def test_structured_doc_masks_values(self):
        text = (
            "Name: John Smith\n"
            "Phone: (555) 123-4567\n"
            "Email: john@example.com\n"
        )
        result = self.pipeline.process_document("struct-2", text, "form")
        assert "John Smith" not in result["anonymized_text"]

    def test_structured_doc_has_entities(self):
        text = "ФИО: Петрова Анна\nТелефон: +7 916 111 22 33\n"
        result = self.pipeline.process_document("struct-3", text, "form")
        assert len(result["entities"]) > 0
