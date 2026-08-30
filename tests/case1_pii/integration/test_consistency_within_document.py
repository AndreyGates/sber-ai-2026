"""Integration test: consistency within document (requires model)."""
import pytest

from pii.config import PipelineConfig
from pii.pipeline import PIIPipeline


@pytest.mark.model
class TestConsistencyWithinDocument:
    @pytest.fixture(autouse=True)
    def setup_pipeline(self):
        self.pipeline = PIIPipeline(PipelineConfig(device="cpu", include_original=True))
        self.pipeline.load_model()

    def test_same_person_gets_same_pseudonym(self):
        text = (
            "Иванов Пётр Сергеевич is the primary account holder.\n"
            "Phone: +7 (912) 345-67-89\n\n"
            "Later, Иванов Пётр Сергеевич confirmed the transaction.\n"
            "The phone +7 (912) 345-67-89 was verified."
        )
        result = self.pipeline.process_document("consist-1", text, "letter")

        name_replacements = [
            r for r in result["replacements"].values()
            if r.get("original") == "Иванов Пётр Сергеевич"
        ]
        if len(name_replacements) >= 2:
            pseudonyms = {r["pseudonym"] for r in name_replacements}
            assert len(pseudonyms) == 1, f"Same name got different pseudonyms: {pseudonyms}"

    def test_same_phone_gets_same_mask(self):
        text = (
            "Call +7 (912) 345-67-89 for info.\n"
            "Or text +7 (912) 345-67-89 anytime."
        )
        result = self.pipeline.process_document("consist-2", text, "ticket")

        phone_replacements = [
            r for r in result["replacements"].values()
            if "+7" in r.get("original", "") and "912" in r.get("original", "")
        ]
        if len(phone_replacements) >= 2:
            pseudonyms = {r["pseudonym"] for r in phone_replacements}
            assert len(pseudonyms) == 1, f"Same phone got different masks: {pseudonyms}"
