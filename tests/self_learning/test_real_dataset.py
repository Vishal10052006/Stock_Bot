from pathlib import Path

import pandas as pd
import pytest

from self_learning.real_dataset import (
    PHASE9_LABELS,
    Phase9DatasetError,
    compare_snapshot_overlap,
    discover_phase9_snapshots,
    inspect_phase9_snapshot,
    load_phase9_dataset,
    validate_snapshot_set,
)


def _frame(labels=None):
    labels = labels or ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"]
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01 09:20", periods=len(labels), freq="5min", tz="Asia/Kolkata"),
            "symbol": ["AAA"] * len(labels),
            "feature_b": range(len(labels)),
            "feature_a": [0.1, 0.2, 0.3][:len(labels)],
            "label": labels,
            "as_of_date": ["2026-01-01"] * len(labels),
        }
    )


def test_discover_phase9_snapshots(tmp_path: Path):
    (tmp_path / "phase9_dataset_20260923T154216Z.parquet").touch()
    (tmp_path / "phase9_dataset_20260922T162520Z.parquet").touch()
    assert discover_phase9_snapshots(tmp_path) == (
        tmp_path / "phase9_dataset_20260922T162520Z.parquet",
        tmp_path / "phase9_dataset_20260923T154216Z.parquet",
    )


def test_discover_requires_directory(tmp_path: Path):
    with pytest.raises(Phase9DatasetError):
        discover_phase9_snapshots(tmp_path / "missing")


def test_discover_requires_snapshot(tmp_path: Path):
    with pytest.raises(Phase9DatasetError):
        discover_phase9_snapshots(tmp_path)


def test_inspect_and_load_phase9_snapshot(tmp_path: Path):
    path = tmp_path / "phase9_dataset_test.parquet"
    frame = _frame()
    frame.to_parquet(path)

    diagnostics = inspect_phase9_snapshot(path)

    assert diagnostics.row_count == 3
    assert diagnostics.feature_columns == ("feature_b", "feature_a")
    assert dict(diagnostics.label_distribution) == {
        "LONG_SUCCESS": 1,
        "NO_EDGE": 1,
        "SHORT_SUCCESS": 1,
    }
    assert diagnostics.duplicate_key_count == 0

    dataset = load_phase9_dataset(path)
    assert dataset.label_column == "label"
    assert dataset.feature_columns == ("feature_b", "feature_a")
    assert list(dataset.data["label"]) == list(frame["label"])


def test_missing_required_column_rejected(tmp_path: Path):
    path = tmp_path / "phase9_dataset_test.parquet"
    frame = _frame().drop(columns=["label"])
    frame.to_parquet(path)

    with pytest.raises(Phase9DatasetError, match="missing required"):
        inspect_phase9_snapshot(path)


def test_unexpected_label_rejected(tmp_path: Path):
    path = tmp_path / "phase9_dataset_test.parquet"
    frame = _frame(["LONG_SUCCESS", "UNKNOWN", "NO_EDGE"])
    frame.to_parquet(path)

    with pytest.raises(Phase9DatasetError, match="unexpected"):
        inspect_phase9_snapshot(path)


def test_duplicate_timestamp_symbol_rejected(tmp_path: Path):
    path = tmp_path / "phase9_dataset_test.parquet"
    frame = _frame()
    frame.loc[1, "timestamp"] = frame.loc[0, "timestamp"]
    frame.to_parquet(path)

    with pytest.raises(Phase9DatasetError, match="duplicate"):
        inspect_phase9_snapshot(path)


def test_null_identifiers_rejected(tmp_path: Path):
    path = tmp_path / "phase9_dataset_test.parquet"
    frame = _frame()
    frame.loc[0, "symbol"] = None
    frame.to_parquet(path)

    with pytest.raises(Phase9DatasetError, match="timestamp and symbol"):
        inspect_phase9_snapshot(path)


def test_missing_features_are_reported_not_silently_filled(tmp_path: Path):
    path = tmp_path / "phase9_dataset_test.parquet"
    frame = _frame()
    frame.loc[0, "feature_a"] = None
    frame.to_parquet(path)

    diagnostics = inspect_phase9_snapshot(path)
    assert dict(diagnostics.missing_counts)["feature_a"] == 1

    dataset = load_phase9_dataset(path)
    assert pd.isna(dataset.data.loc[0, "feature_a"])


def test_snapshot_overlap_is_reported_without_merging(tmp_path: Path):
    left = tmp_path / "phase9_dataset_left.parquet"
    right = tmp_path / "phase9_dataset_right.parquet"

    _frame().to_parquet(left)
    right_frame = _frame().iloc[1:].copy()
    right_frame.to_parquet(right)

    overlap = compare_snapshot_overlap(left, right)
    assert overlap.overlapping_keys == 2


def test_snapshot_set_reports_pairwise_overlap(tmp_path: Path):
    left = tmp_path / "phase9_dataset_left.parquet"
    right = tmp_path / "phase9_dataset_right.parquet"
    _frame().to_parquet(left)
    _frame().to_parquet(right)

    overlaps = validate_snapshot_set([left, right])
    assert len(overlaps) == 1
    assert overlaps[0].overlapping_keys == 3


def test_allowed_labels_are_explicit():
    assert PHASE9_LABELS == {"LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"}
