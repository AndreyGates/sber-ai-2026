"""Unit tests for replacement strategies (design.md Decision 8, level 1)."""
from pii.registry import PseudonymRegistry
from pii.strategies import get_replacement


class TestReplacementStrategies:
    def setup_method(self):
        self.registry = PseudonymRegistry(doc_id="test-doc")

    def test_person_name_returns_pseudonym(self):
        result = get_replacement("Иванов Пётр Сергеевич", "PERSON_NAME", "test-doc", self.registry)
        assert result != "Иванов Пётр Сергеевич"
        assert len(result) > 0

    def test_phone_masking_preserves_format(self):
        result = get_replacement("+7 (912) 345-67-89", "PHONE_NUMBER", "test-doc", self.registry)
        assert "+" in result or result.startswith("+") or "*" in result
        assert len(result) == len("+7 (912) 345-67-89")

    def test_email_preserves_domain(self):
        result = get_replacement("ivan.petrov@bank.ru", "EMAIL", "test-doc", self.registry)
        assert "@bank.ru" in result
        assert "ivan.petrov" not in result

    def test_card_masking_shows_last_four(self):
        result = get_replacement("4111111111111111", "CARD_NUMBER", "test-doc", self.registry)
        assert result.endswith("1111")
        assert "*" in result

    def test_gov_id_masking(self):
        result = get_replacement("4510 123456", "GOV_ID", "test-doc", self.registry)
        assert "*" in result
        assert len(result) == len("4510 123456")

    def test_healthcare_data_generic_label(self):
        result = get_replacement("диагноз: грипп", "HEALTHCARE_DATA", "test-doc", self.registry)
        assert result == "[МЕДИЦИНСКИЕ ДАННЫЕ]"

    def test_address_returns_pseudonym(self):
        result = get_replacement("ул. Ленина, д.5, кв.12", "ADDRESS", "test-doc", self.registry)
        assert "ул. Ленина" not in result
        assert len(result) > 0

    def test_date_of_birth_generalization(self):
        result = get_replacement("14.03.1985", "DATE_OF_BIRTH", "test-doc", self.registry)
        assert "1985" not in result
        assert "." in result

    def test_mask_action_for_high_risk(self):
        result = get_replacement(
            "4510 123456", "GOV_ID", "test-doc", self.registry, action="mask",
        )
        assert "*" in result
        assert len(result) == len("4510 123456")

    def test_account_number_masking(self):
        result = get_replacement("1234567890123456", "ACCOUNT_NUMBER", "test-doc", self.registry)
        assert "*" in result

    def test_consistent_pseudonym_for_same_input(self):
        r1 = get_replacement("Иванов Пётр", "PERSON_NAME", "test-doc", self.registry)
        r2 = get_replacement("Иванов Пётр", "PERSON_NAME", "test-doc", self.registry)
        assert r1 == r2


class TestEnglishLocaleStrategies:
    def setup_method(self):
        self.registry = PseudonymRegistry(doc_id="test-doc-en", locale="en")

    def test_en_person_name_english_chars(self):
        result = get_replacement("John Smith", "PERSON_NAME", "test-doc-en", self.registry)
        assert result != "John Smith"
        assert all(ord(c) < 0x400 for c in result)

    def test_en_healthcare_label(self):
        result = get_replacement("Type 2 Diabetes", "HEALTHCARE_DATA", "test-doc-en", self.registry)
        assert result == "[MEDICAL DATA]"

    def test_en_address_us_format(self):
        result = get_replacement("123 Main St, Springfield, IL", "ADDRESS", "test-doc-en", self.registry)
        assert "Springfield" not in result
        assert any(s in result for s in ("St", "Ave", "Dr", "Ln", "Rd", "Blvd"))

    def test_en_date_us_format(self):
        result = get_replacement("05/12/1990", "DATE_OF_BIRTH", "test-doc-en", self.registry)
        assert "/" in result
        assert result != "05/12/1990"

    def test_en_mask_healthcare(self):
        result = get_replacement(
            "diabetes type 2", "HEALTHCARE_DATA", "test-doc-en", self.registry, action="mask",
        )
        assert result == "[MEDICAL DATA]"

    def test_en_organization(self):
        result = get_replacement("Acme Corp", "ORGANIZATION", "test-doc-en", self.registry)
        assert result != "Acme Corp"
        assert result in ("Acme Corp", "GlobalTech Inc", "Summit Solutions LLC",
                          "Pinnacle Group", "Vertex Systems", "Apex Industries") or len(result) > 0
