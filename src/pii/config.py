from __future__ import annotations

from dataclasses import dataclass, field


MODEL_NAME = "OpenMed/privacy-filter-nemotron"
MODEL_REVISION = "main"

HIGH_RISK_CATEGORIES: frozenset[str] = frozenset({
    "GOV_ID",
    "FINANCIAL_ACCOUNT",
    "HEALTHCARE_DATA",
    "DOCUMENT_NUMBER",
    "ACCOUNT_NUMBER",
    "CARD_NUMBER",
    "POLICY_NUMBER",
    "SSN",
    "PASSPORT_NUMBER",
    "DRIVER_LICENSE",
    "TAX_ID",
    "MEDICAL_RECORD",
    "INSURANCE_NUMBER",
    "ROUTING_NUMBER",
    "IBAN",
    "BIC",
    # Fine-grained labels from OpenMed/privacy-filter-nemotron
    "ssn",
    "credit_debit_card",
    "bank_routing_number",
    "account_number",
    "swift_bic",
    "medical_record_number",
    "health_plan_beneficiary_number",
    "certificate_license_number",
    "cvv",
    "pin",
    "password",
    "biometric_identifier",
})


@dataclass(frozen=True)
class PipelineConfig:
    model_name: str = MODEL_NAME
    model_revision: str = MODEL_REVISION
    max_length: int = 512
    overlap: int = 64
    batch_size: int = 8
    device: str = "cpu"
    dtype: str = "float32"

    min_score: float = 0.5
    high_confidence_threshold: float = 0.85

    high_risk_categories: frozenset[str] = field(
        default_factory=lambda: frozenset(HIGH_RISK_CATEGORIES),
    )

    fuzzy_name_threshold: float = 0.8

    include_original: bool = True
