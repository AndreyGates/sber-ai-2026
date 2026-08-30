"""Unit tests for pseudonym registry (design.md Decision 8, level 1)."""
from pii.normalize import fuzzy_match_names, normalize_value
from pii.registry import PseudonymRegistry


class TestNormalization:
    def test_casefold(self):
        assert normalize_value("Иванов") == normalize_value("иванов")

    def test_whitespace_collapse(self):
        assert normalize_value("Иванов  Пётр") == normalize_value("Иванов Пётр")

    def test_leading_trailing_spaces(self):
        assert normalize_value("  Иванов  ") == normalize_value("Иванов")

    def test_tabs_and_newlines(self):
        assert normalize_value("Иванов\tПётр\nСергеевич") == normalize_value("Иванов Пётр Сергеевич")


class TestFuzzyMatchNames:
    def test_exact_match(self):
        result = fuzzy_match_names(["Иванов И.И.", "Иванов И.И."])
        assert result["Иванов И.И."] == "Иванов И.И."

    def test_similar_names_clustered(self):
        result = fuzzy_match_names(
            ["Иванов Пётр Сергеевич", "Пётр Сергеевич Иванов"],
            threshold=0.7,
        )
        rep = result["Иванов Пётр Сергеевич"]
        assert result["Пётр Сергеевич Иванов"] == rep

    def test_different_names_not_clustered(self):
        result = fuzzy_match_names(["Иванов", "Петров"], threshold=0.8)
        assert result["Иванов"] == "Иванов"
        assert result["Петров"] == "Петров"

    def test_empty_list(self):
        assert fuzzy_match_names([]) == {}


class TestPseudonymRegistry:
    def test_deterministic(self):
        reg1 = PseudonymRegistry(doc_id="doc1")
        reg2 = PseudonymRegistry(doc_id="doc1")
        p1 = reg1.get_pseudonym("Иванов Пётр", "PERSON_NAME")
        p2 = reg2.get_pseudonym("Иванов Пётр", "PERSON_NAME")
        assert p1 == p2

    def test_same_value_same_pseudonym(self):
        reg = PseudonymRegistry(doc_id="doc1")
        p1 = reg.get_pseudonym("Иванов Пётр", "PERSON_NAME")
        p2 = reg.get_pseudonym("Иванов Пётр", "PERSON_NAME")
        assert p1 == p2

    def test_case_insensitive_dedup(self):
        reg = PseudonymRegistry(doc_id="doc1")
        p1 = reg.get_pseudonym("Иванов Пётр", "PERSON_NAME")
        p2 = reg.get_pseudonym("иванов пётр", "PERSON_NAME")
        assert p1 == p2

    def test_isolation_between_documents(self):
        reg1 = PseudonymRegistry(doc_id="doc1")
        reg2 = PseudonymRegistry(doc_id="doc2")
        p1 = reg1.get_pseudonym("Иванов Пётр", "PERSON_NAME")
        p2 = reg2.get_pseudonym("Иванов Пётр", "PERSON_NAME")
        assert p1 != p2

    def test_different_categories_different_pseudonyms(self):
        reg = PseudonymRegistry(doc_id="doc1")
        p1 = reg.get_pseudonym("some_value", "PERSON_NAME")
        p2 = reg.get_pseudonym("some_value", "ADDRESS")
        assert p1 != p2

    def test_get_all(self):
        reg = PseudonymRegistry(doc_id="doc1")
        reg.get_pseudonym("value1", "PERSON_NAME")
        reg.get_pseudonym("value2", "EMAIL")
        all_items = reg.get_all()
        assert len(all_items) == 2


class TestEnglishLocale:
    def test_en_person_name_no_patronymic(self):
        reg = PseudonymRegistry(doc_id="doc-en", locale="en")
        name = reg.get_pseudonym("John Smith", "PERSON_NAME")
        parts = name.split()
        assert len(parts) == 2
        assert all(ord(c) < 0x400 for c in name)

    def test_en_address_us_format(self):
        reg = PseudonymRegistry(doc_id="doc-en", locale="en")
        addr = reg.get_pseudonym("123 Main St", "ADDRESS")
        assert any(street in addr for street in ("St", "Ave", "Dr", "Ln", "Rd", "Blvd"))

    def test_en_date_mm_dd_yyyy(self):
        reg = PseudonymRegistry(doc_id="doc-en", locale="en")
        date = reg.get_pseudonym("05/12/1990", "DATE_OF_BIRTH")
        assert "/" in date
        assert date.endswith("/1990")

    def test_en_healthcare_label(self):
        reg = PseudonymRegistry(doc_id="doc-en", locale="en")
        label = reg.get_pseudonym("diabetes", "HEALTHCARE_DATA")
        assert label == "[MEDICAL DATA]"

    def test_en_organization(self):
        reg = PseudonymRegistry(doc_id="doc-en", locale="en")
        org = reg.get_pseudonym("Some Company", "ORGANIZATION")
        assert any(cyrillic in org for cyrillic in ("ООО", "АО", "ПАО")) is False

    def test_en_deterministic(self):
        reg1 = PseudonymRegistry(doc_id="doc-en", locale="en")
        reg2 = PseudonymRegistry(doc_id="doc-en", locale="en")
        assert reg1.get_pseudonym("John", "PERSON_NAME") == reg2.get_pseudonym("John", "PERSON_NAME")

    def test_en_ru_produce_different_names(self):
        reg_en = PseudonymRegistry(doc_id="doc1", locale="en")
        reg_ru = PseudonymRegistry(doc_id="doc1", locale="ru")
        name_en = reg_en.get_pseudonym("John Smith", "PERSON_NAME")
        name_ru = reg_ru.get_pseudonym("John Smith", "PERSON_NAME")
        assert name_en != name_ru

    def test_default_locale_is_russian(self):
        reg = PseudonymRegistry(doc_id="doc1")
        name = reg.get_pseudonym("Test", "PERSON_NAME")
        assert any(ord(c) >= 0x400 for c in name)
