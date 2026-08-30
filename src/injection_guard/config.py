from dataclasses import dataclass, field

MODEL_ID = "protectai/deberta-v3-base-prompt-injection-v2"
DATASET_ID = "jayavibhav/prompt-injection-safety"

CLASS_SAFE = "safe"
CLASS_INJECTION = "injection and malicious"

DECISION_PASS = "пропустить"
DECISION_BLOCK = "заблокировать"
DECISION_REVIEW = "ручная проверка"


@dataclass
class PipelineConfig:
    t_low: float = 0.15
    t_high: float = 0.75
    batch_size: int = 32
    max_length: int = 512
    model_id: str = MODEL_ID
    dataset_id: str = DATASET_ID
    test_sample: int | None = None


# --- class mapping (Decision 2) ---

DATASET_LABEL_MAP: dict[int, str] = {
    0: CLASS_SAFE,
    1: CLASS_INJECTION,
    2: CLASS_INJECTION,
}

MODEL_LABEL_MAP: dict[int, str] = {
    0: CLASS_SAFE,
    1: CLASS_INJECTION,
}


def map_dataset_label(label: int) -> str:
    return DATASET_LABEL_MAP[label]


def map_model_label(label: int) -> str:
    return MODEL_LABEL_MAP[label]
