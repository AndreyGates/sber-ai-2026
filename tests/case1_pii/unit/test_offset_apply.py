"""Unit tests for offset-based replacement application (design.md Decision 8, level 1)."""
from pii.apply import apply_replacements
from pii.bioes import Entity


class TestApplyReplacements:
    def test_single_replacement(self):
        text = "Hello Ivan Petrov, welcome!"
        entity = Entity("PERSON_NAME", 6, 17, 0.9)
        result = apply_replacements(text, [(entity, "John Smith")])
        assert result == "Hello John Smith, welcome!"

    def test_multiple_replacements_different_lengths(self):
        text = "Name: Ivan Petrov, Email: ivan@example.com"
        entities = [
            (Entity("PERSON_NAME", 6, 17, 0.9), "A"),
            (Entity("EMAIL", 26, 42, 0.8), "B@C.D"),
        ]
        result = apply_replacements(text, entities)
        assert "Name: A, Email: B@C.D" == result

    def test_replacement_longer_than_original(self):
        text = "Hi Al"
        entity = Entity("PERSON_NAME", 3, 5, 0.9)
        result = apply_replacements(text, [(entity, "Alexander")])
        assert result == "Hi Alexander"

    def test_replacement_shorter_than_original(self):
        text = "Hi Alexander"
        entity = Entity("PERSON_NAME", 3, 12, 0.9)
        result = apply_replacements(text, [(entity, "Al")])
        assert result == "Hi Al"

    def test_entity_at_start(self):
        text = "Ivan Petrov is here"
        entity = Entity("PERSON_NAME", 0, 11, 0.9)
        result = apply_replacements(text, [(entity, "X")])
        assert result == "X is here"

    def test_entity_at_end(self):
        text = "Hello Ivan Petrov"
        entity = Entity("PERSON_NAME", 6, 17, 0.9)
        result = apply_replacements(text, [(entity, "X")])
        assert result == "Hello X"

    def test_adjacent_entities(self):
        text = "IvanPetrov"
        entities = [
            (Entity("FIRST", 0, 4, 0.9), "A"),
            (Entity("LAST", 4, 10, 0.9), "B"),
        ]
        result = apply_replacements(text, entities)
        assert result == "AB"

    def test_no_replacements(self):
        text = "No PII here"
        result = apply_replacements(text, [])
        assert result == "No PII here"

    def test_three_replacements_mixed_lengths(self):
        text = "AAA BBB CCC"
        entities = [
            (Entity("X", 0, 3, 0.9), "XXXXXX"),
            (Entity("Y", 4, 7, 0.9), "Y"),
            (Entity("Z", 8, 11, 0.9), "ZZZZ"),
        ]
        result = apply_replacements(text, entities)
        assert result == "XXXXXX Y ZZZZ"
