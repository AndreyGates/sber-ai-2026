"""Category-aware replacement strategies (design.md Decision 5)."""
from __future__ import annotations

import re

from pii.registry import PseudonymRegistry, _is_english_locale


def get_replacement(
    original: str,
    category: str,
    doc_id: str,
    registry: PseudonymRegistry,
    action: str = "replace",
) -> str:
    """Get the replacement string for a PII entity based on its category and policy action.

    Args:
        original: the original PII text
        category: PII category label
        doc_id: document identifier (for registry isolation)
        registry: pseudonym registry for this document
        action: 'replace' for full replacement, 'mask' for partial masking
    """
    if action == "mask":
        return _mask_by_category(original, category, locale=registry.locale)

    return _replace_by_category(original, category, doc_id, registry)


def _replace_by_category(
    original: str,
    category: str,
    doc_id: str,
    registry: PseudonymRegistry,
) -> str:
    if category in ("PERSON_NAME", "PERSON", "NAME",
                     "first_name", "last_name", "middle_name",
                     "full_name", "user_name"):
        return registry.get_pseudonym(original, category)

    if category in ("PHONE_NUMBER", "PHONE", "phone_number", "fax_number"):
        return _mask_phone(original)

    if category in ("EMAIL", "email"):
        return _mask_email(original)

    if category in ("CARD_NUMBER", "credit_debit_card"):
        return _mask_card(original)

    if category in ("GOV_ID", "DOCUMENT_NUMBER", "PASSPORT_NUMBER", "DRIVER_LICENSE",
                     "ssn", "certificate_license_number"):
        return _mask_gov_id(original)

    if category in ("ACCOUNT_NUMBER", "FINANCIAL_ACCOUNT", "IBAN", "ROUTING_NUMBER", "BIC",
                     "account_number", "bank_routing_number", "swift_bic",
                     "POLICY_NUMBER", "INSURANCE_NUMBER"):
        return _mask_account(original)

    if category in ("DATE_OF_BIRTH", "DATE", "date", "date_of_birth", "date_time"):
        return registry.get_pseudonym(original, category)

    if category in ("ADDRESS", "street_address", "city", "state",
                     "country", "county", "postcode"):
        return registry.get_pseudonym(original, category)

    if category in ("HEALTHCARE_DATA", "MEDICAL_RECORD", "DIAGNOSIS",
                     "medical_record_number", "health_plan_beneficiary_number",
                     "blood_type"):
        return "[MEDICAL DATA]" if _is_english_locale(registry.locale) else "[МЕДИЦИНСКИЕ ДАННЫЕ]"

    if category in ("ORGANIZATION", "COMPANY", "company_name"):
        return registry.get_pseudonym(original, category)

    if category in ("SSN", "TAX_ID"):
        return _mask_gov_id(original)

    return registry.get_pseudonym(original, category)


def _mask_by_category(original: str, category: str, locale: str = "ru") -> str:
    if category in ("PHONE_NUMBER", "PHONE", "phone_number", "fax_number"):
        return _mask_phone(original)
    if category in ("CARD_NUMBER", "credit_debit_card"):
        return _mask_card(original)
    if category in ("GOV_ID", "DOCUMENT_NUMBER", "PASSPORT_NUMBER", "DRIVER_LICENSE",
                     "SSN", "TAX_ID", "ssn", "certificate_license_number"):
        return _mask_gov_id(original)
    if category in ("ACCOUNT_NUMBER", "FINANCIAL_ACCOUNT", "IBAN", "ROUTING_NUMBER", "BIC",
                     "POLICY_NUMBER", "INSURANCE_NUMBER",
                     "account_number", "bank_routing_number", "swift_bic"):
        return _mask_account(original)
    if category in ("EMAIL", "email"):
        return _mask_email(original)
    if category in ("HEALTHCARE_DATA", "MEDICAL_RECORD", "DIAGNOSIS",
                     "medical_record_number", "health_plan_beneficiary_number",
                     "blood_type"):
        return "[MEDICAL DATA]" if _is_english_locale(locale) else "[МЕДИЦИНСКИЕ ДАННЫЕ]"
    return _mask_generic(original)


def _mask_phone(text: str) -> str:
    digits = list(text)
    digit_count = 0
    for i, ch in enumerate(digits):
        if ch.isdigit():
            digit_count += 1
    visible = max(2, digit_count // 4)
    shown = 0
    result = list(text)
    for i in range(len(result) - 1, -1, -1):
        if result[i].isdigit():
            if shown < visible:
                shown += 1
            else:
                result[i] = "*"
    return "".join(result)


def _mask_email(text: str) -> str:
    parts = text.split("@", 1)
    if len(parts) != 2:
        return _mask_generic(text)
    local = parts[0]
    domain = parts[1]
    if len(local) <= 2:
        masked_local = local[0] + "*" * max(1, len(local) - 1)
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _mask_card(text: str) -> str:
    digits = re.findall(r"\d", text)
    if len(digits) < 4:
        return _mask_generic(text)
    last4 = "".join(digits[-4:])
    non_digit_positions = []
    digit_positions = []
    for i, ch in enumerate(text):
        if ch.isdigit():
            digit_positions.append(i)
        else:
            non_digit_positions.append(i)

    result = list(text)
    visible_count = 4
    digits_to_mask = len(digit_positions) - visible_count
    for j, pos in enumerate(digit_positions):
        if j < digits_to_mask:
            result[pos] = "*"
    return "".join(result)


def _mask_gov_id(text: str) -> str:
    digits = re.findall(r"\d", text)
    if len(digits) <= 2:
        return _mask_generic(text)
    result = list(text)
    digit_positions = [i for i, ch in enumerate(text) if ch.isdigit()]
    visible = min(2, len(digit_positions))
    for j, pos in enumerate(digit_positions):
        if j < len(digit_positions) - visible:
            result[pos] = "*"
    return "".join(result)


def _mask_account(text: str) -> str:
    return _mask_gov_id(text)


def _mask_generic(text: str) -> str:
    if len(text) <= 2:
        return "*" * len(text)
    return text[0] + "*" * (len(text) - 2) + text[-1]
