"""Tests for the real Phase-9 DatasetVersion provenance builder."""

from pathlib import Path

import pandas as pd
import pytest

from self_learning.provenance import build_phase9_dataset_version
from self_learning.real_dataset import Phase9DatasetError


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01 09:20",
                periods=3,
                freq="5min",
                tz="Asia/Kolkata",
            ),
            "symbol": ["AAA", "AAA", "BBB"],
            "feature_b": [1.0, 2.0, 3.0],
            "feature_a": [0.1, 0.2, 0.3],
            "label": ["LONG_SUCCESS", "NO_EDGE", "SHORT_SUCCESS"],
            "as_of_date": ["2026-01-01"] * 3,
        }
    )


def test_build_phase9_dataset_version_uses_exact_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "phase9_dataset_test.parquet"
    _frame().to_parquet(path)

    version = build_phase9_dataset_version(
        path,
        dataset_version="phase9-test-v1",
        source="phase9_dataset_test.parquet",
        creation_timestamp="2026-09-24T20:00:00+05:30",
        feature_schema_version="phase9-features-v1",
        label_definition_version="phase9-labels-v1",
        known_limitations=("synthetic test snapshot",),
    )

    assert version.dataset_version == "phase9-test-v1"
    assert version.source == "phase9_dataset_test.parquet"
    assert version.row_count == 3
    assert version.symbols == ("AAA", "BBB")
    assert version.period_start.startswith("2026-01-01T09:20:00")
    assert version.period_end.startswith("2026-01-01T09:30:00")
    assert dict(version.label_distribution) == {
        "LONG_SUCCESS": 1,
        "NO_EDGE": 1,
        "SHORT_SUCCESS": 1,
    }
    assert version.feature_schema_version == "phase9-features-v1"
    assert version.label_definition_version == "phase9-labels-v1"
    assert len(version.source_fingerprints) == 1
    assert len(version.source_fingerprints[0]) == 64
    assert version.known_limitations == ("synthetic test snapshot",)


def test_same_snapshot_produces_same_source_identity(tmp_path: Path) -> None:
    path = tmp_path / "phase9_dataset_test.parquet"
    _frame().to_parquet(path)

    kwargs = {
        "dataset_version": "phase9-test-v1",
        "source": "phase9_dataset_test.parquet",
        "creation_timestamp": "2026-09-24T20:00:00+05:30",
        "feature_schema_version": "phase9-features-v1",
        "label_definition_version": "phase9-labels-v1",
    }

    first = build_phase9_dataset_version(path, **kwargs)
    second = build_phase9_dataset_version(path, **kwargs)

    assert first.source_fingerprints == second.source_fingerprints
    assert first.fingerprint == second.fingerprint


def test_changed_snapshot_gets_different_source_identity(tmp_path: Path) -> None:
    path = tmp_path / "phase9_dataset_test.parquet"
    frame = _frame()
    frame.to_parquet(path)

    first = build_phase9_dataset_version(
        path,
        dataset_version="phase9-test-v1",
        source="phase9_dataset_test.parquet",
        creation_timestamp="2026-09-24T20:00:00+05:30",
        feature_schema_version="phase9-features-v1",
        label_definition_version="phase9-labels-v1",
    )

    changed = frame.copy()
    changed.loc[0, "feature_a"] = 999.0
    changed.to_parquet(path)

    second = build_phase9_dataset_version(
        path,
        dataset_version="phase9-test-v1",
        source="phase9_dataset_test.parquet",
        creation_timestamp="2026-09-24T20:00:00+05:30",
        feature_schema_version="phase9-features-v1",
        label_definition_version="phase9-labels-v1",
    )

    assert first.source_fingerprints != second.source_fingerprints


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dataset_version", ""),
        ("source", ""),
        ("creation_timestamp", ""),
        ("feature_schema_version", ""),
        ("label_definition_version", ""),
    ],
)
def test_provenance_metadata_is_explicit(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    path = tmp_path / "phase9_dataset_test.parquet"
    _frame().to_parquet(path)

    kwargs = {
        "dataset_version": "phase9-test-v1",
        "source": "phase9_dataset_test.parquet",
        "creation_timestamp": "2026-09-24T20:00:00+05:30",
        "feature_schema_version": "phase9-features-v1",
        "label_definition_version": "phase9-labels-v1",
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match="must not be empty"):
        build_phase9_dataset_version(path, **kwargs)


def test_invalid_snapshot_cannot_receive_provenance(tmp_path: Path) -> None:
    path = tmp_path / "phase9_dataset_test.parquet"
    frame = _frame().drop(columns=["label"])
    frame.to_parquet(path)

    with pytest.raises(Phase9DatasetError, match="missing required"):
        build_phase9_dataset_version(
            path,
            dataset_version="phase9-test-v1",
            source="phase9_dataset_test.parquet",
            creation_timestamp="2026-09-24T20:00:00+05:30",
            feature_schema_version="phase9-features-v1",
            label_definition_version="phase9-labels-v1",
        )


def test_provenance_builder_does_not_clean_missing_features(tmp_path: Path) -> None:
    path = tmp_path / "phase9_dataset_test.parquet"
    frame = _frame()
    frame.loc[1, "feature_a"] = None
    frame.to_parquet(path)

    version = build_phase9_dataset_version(
        path,
        dataset_version="phase9-test-v1",
        source="phase9_dataset_test.parquet",
        creation_timestamp="2026-09-24T20:00:00+05:30",
        feature_schema_version="phase9-features-v1",
        label_definition_version="phase9-labels-v1",
    )

    assert version.row_count == 3
    assert len(version.source_fingerprints) == 1
