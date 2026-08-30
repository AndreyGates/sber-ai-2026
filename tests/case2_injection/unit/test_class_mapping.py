from injection_guard.config import (
    CLASS_INJECTION,
    CLASS_SAFE,
    map_dataset_label,
    map_model_label,
)


class TestDatasetLabelMapping:
    def test_benign_maps_to_safe(self):
        assert map_dataset_label(0) == CLASS_SAFE

    def test_injection_maps_to_injection_and_malicious(self):
        assert map_dataset_label(1) == CLASS_INJECTION

    def test_harmful_maps_to_injection_and_malicious(self):
        assert map_dataset_label(2) == CLASS_INJECTION


class TestModelLabelMapping:
    def test_benign_maps_to_safe(self):
        assert map_model_label(0) == CLASS_SAFE

    def test_injection_detected_maps_to_injection_and_malicious(self):
        assert map_model_label(1) == CLASS_INJECTION
