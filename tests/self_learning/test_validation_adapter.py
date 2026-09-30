"""Tests for existing validation adapters used by self-learning."""

import pandas as pd
import pytest

from self_learning.validation_adapter import summarize_artifact, validate_dataset_boundary


def test_dataset_boundary_adapter_runs_existing_leakage_checks() -> None:
    data = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01 09:15",
                periods=3,
                freq="5min",
                tz="Asia/Kolkata",
            ),
            "symbol": ["ITC"] * 3,
            "feature_a": [1.0, 2.0, 3.0],
            "label": ["NO_EDGE", "LONG_SUCCESS", "SHORT_SUCCESS"],
        }
    )

    summary = validate_dataset_boundary(
        data,
        feature_columns=("feature_a",),
    )

    assert summary.stage == "LEAKAGE_AUDIT"
    assert summary.valid
    assert summary.observations == 3


def test_dataset_boundary_adapter_blocks_future_named_feature() -> None:
    data = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01 09:15",
                periods=2,
                freq="5min",
                tz="Asia/Kolkata",
            ),
            "symbol": ["ITC"] * 2,
            "future_return": [1.0, 2.0],
            "label": ["NO_EDGE", "LONG_SUCCESS"],
        }
    )

    summary = validate_dataset_boundary(
        data,
        feature_columns=("future_return",),
    )

    assert not summary.valid
    assert "feature_name_screen" in summary.issues


def test_summarize_artifact_requires_sha256() -> None:
    class Artifact:
        fingerprint = "not-sha"

    with pytest.raises(ValueError, match="SHA-256"):
        summarize_artifact("OOS", Artifact(), observations=1)
