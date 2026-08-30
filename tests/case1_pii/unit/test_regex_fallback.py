"""Unit tests for regex fallback (design.md Decision 8, level 1)."""
from pii.bioes import Entity
from pii.regex_fallback import luhn_check, regex_fallback


class TestLuhnCheck:
    def test_valid_visa(self):
        assert luhn_check("4111111111111111") is True

    def test_valid_mastercard(self):
        assert luhn_check("5500000000000004") is True

    def test_invalid_number(self):
        assert luhn_check("4111111111111112") is False

    def test_too_short(self):
        assert luhn_check("123") is False

    def test_with_spaces(self):
        assert luhn_check("4111 1111 1111 1111") is True

    def test_with_dashes(self):
        assert luhn_check("4111-1111-1111-1111") is True


class TestRegexFallback:
    def test_detects_email(self):
        text = "Contact me at john.doe@example.com please"
        result = regex_fallback(text, [])
        emails = [e for e in result if e.label == "EMAIL"]
        assert len(emails) == 1
        assert text[emails[0].start:emails[0].end] == "john.doe@example.com"

    def test_detects_phone(self):
        text = "Call me at +7 (912) 345-67-89 today"
        result = regex_fallback(text, [])
        phones = [e for e in result if e.label == "PHONE_NUMBER"]
        assert len(phones) >= 1

    def test_detects_valid_card(self):
        text = "Card number: 4111111111111111"
        result = regex_fallback(text, [])
        cards = [e for e in result if e.label == "CARD_NUMBER"]
        assert len(cards) == 1

    def test_skips_invalid_luhn_card(self):
        text = "Not a card: 4111111111111112"
        result = regex_fallback(text, [])
        cards = [e for e in result if e.label == "CARD_NUMBER"]
        assert len(cards) == 0

    def test_skips_already_covered_email(self):
        text = "Email: john@example.com"
        existing = [Entity("EMAIL", 7, 25, 0.95)]
        result = regex_fallback(text, existing)
        emails = [e for e in result if e.label == "EMAIL"]
        assert len(emails) == 0

    def test_no_false_positives_on_plain_text(self):
        text = "This is a regular sentence with no PII at all."
        result = regex_fallback(text, [])
        assert len(result) == 0

    def test_multiple_emails(self):
        text = "a@b.com and c@d.org"
        result = regex_fallback(text, [])
        emails = [e for e in result if e.label == "EMAIL"]
        assert len(emails) == 2
