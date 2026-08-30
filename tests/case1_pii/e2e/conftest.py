"""Shared fixtures for e2e and integration tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def fixture_documents():
    with (FIXTURES_DIR / "documents.json").open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def fixture_documents_with_pii(fixture_documents):
    return [d for d in fixture_documents if d.get("known_pii")]


@pytest.fixture
def pipeline_config():
    from pii.config import PipelineConfig
    return PipelineConfig(
        min_score=0.5,
        high_confidence_threshold=0.85,
        include_original=False,
    )
