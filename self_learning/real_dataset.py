"""Real Phase-9 dataset adapter for the self-learning engine.

This module is deliberately narrow: it converts one explicit Phase-9 parquet
snapshot into the existing ML TrainingDataset contract after validating schema,
labels, identifiers, duplicates, and missing-value diagnostics.

It never mutates the source file and never concatenates snapshots implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from ml.datasets.models import TrainingDataset


PHASE9_REQUIRED_COLUMNS = frozenset({"timestamp", "symbol", "label", "as_of_date"})
PHASE9_LABELS = frozenset({"LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"})
PHASE9_METADATA_COLUMNS = frozenset({"timestamp", "symbol", "label", "as_of_date"})


@dataclass(frozen=True)
class DatasetDiagnostics:
    """Immutable diagnostics produced while validating one snapshot."""

    source_path: str
    row_count: int
    feature_columns: tuple[str, ...]
    label_distribution: tuple[tuple[str, int], ...]
    duplicate_key_count: int
    missing_counts: tuple[tuple[str, int], ...]
    missing_rate_by_column: tuple[tuple[str, float], ...]
    period_start: str
    period_end: str

    @property
    def has_duplicates(self) -> bool:
        return self.duplicate_key_count > 0


@dataclass(frozen=True)
class SnapshotOverlap:
    """Overlap diagnostics between two Phase-9 snapshots."""

    left_path: str
    right_path: str
    overlapping_keys: int


class Phase9DatasetError(ValueError):
    """Raised when a Phase-9 snapshot violates the learning input contract."""


def discover_phase9_snapshots(root: str | Path) -> tuple[Path, ...]:
    """Discover Phase-9 feature/label snapshots without selecting one."""
    directory = Path(root)
    if not directory.exists():
        raise Phase9DatasetError(f"dataset directory does not exist: {directory}")
    if not directory.is_dir():
        raise Phase9DatasetError(f"dataset path is not a directory: {directory}")

    paths = tuple(sorted(directory.glob("phase9_dataset_*.parquet")))
    if not paths:
        raise Phase9DatasetError(
            f"no Phase-9 dataset snapshots found in {directory}"
        )
    return paths


def _validate_columns(frame: pd.DataFrame) -> None:
    missing = sorted(PHASE9_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise Phase9DatasetError(
            f"missing required Phase-9 columns: {missing}"
        )

    feature_columns = [
        column for column in frame.columns
        if column not in PHASE9_METADATA_COLUMNS
    ]
    if not feature_columns:
        raise Phase9DatasetError("Phase-9 dataset contains no feature columns")


def _validate_labels(frame: pd.DataFrame) -> None:
    if frame["label"].isna().any():
        raise Phase9DatasetError("label column contains null values")

    observed = {str(value) for value in frame["label"].unique()}
    unexpected = sorted(observed - PHASE9_LABELS)
    if unexpected:
        raise Phase9DatasetError(
            f"unexpected Phase-9 labels: {unexpected}; "
            f"allowed labels: {sorted(PHASE9_LABELS)}"
        )


def _validate_identifiers(frame: pd.DataFrame) -> None:
    if frame["timestamp"].isna().any() or frame["symbol"].isna().any():
        raise Phase9DatasetError("timestamp and symbol must not contain null values")

    timestamps = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    if timestamps.isna().any():
        raise Phase9DatasetError("timestamp contains invalid datetime values")

    symbols = frame["symbol"].astype(str).str.strip()
    if (symbols == "").any():
        raise Phase9DatasetError("symbol contains empty values")


def _duplicate_key_count(frame: pd.DataFrame) -> int:
    return int(frame.duplicated(subset=["timestamp", "symbol"], keep=False).sum())


def inspect_phase9_snapshot(path: str | Path) -> DatasetDiagnostics:
    """Validate and inspect one explicit Phase-9 parquet snapshot."""
    source = Path(path)
    if not source.exists():
        raise Phase9DatasetError(f"dataset file does not exist: {source}")
    if source.suffix.lower() != ".parquet":
        raise Phase9DatasetError(f"expected a parquet file: {source}")

    frame = pd.read_parquet(source)
    if frame.empty:
        raise Phase9DatasetError(f"dataset is empty: {source}")

    _validate_columns(frame)
    _validate_labels(frame)
    _validate_identifiers(frame)

    duplicates = _duplicate_key_count(frame)
    if duplicates:
        raise Phase9DatasetError(
            f"dataset contains {duplicates} rows participating in duplicate "
            "(timestamp, symbol) keys"
        )

    timestamps = pd.to_datetime(frame["timestamp"], utc=True)
    feature_columns = tuple(
        column for column in frame.columns
        if column not in PHASE9_METADATA_COLUMNS
    )
    missing_counts = tuple(
        (str(column), int(frame[column].isna().sum()))
        for column in frame.columns
        if int(frame[column].isna().sum()) > 0
    )
    missing_rates = tuple(
        (str(column), float(frame[column].isna().mean()))
        for column in frame.columns
        if int(frame[column].isna().sum()) > 0
    )
    labels = frame["label"].astype(str).value_counts().sort_index()

    return DatasetDiagnostics(
        source_path=str(source),
        row_count=len(frame),
        feature_columns=feature_columns,
        label_distribution=tuple(
            (str(label), int(count)) for label, count in labels.items()
        ),
        duplicate_key_count=duplicates,
        missing_counts=missing_counts,
        missing_rate_by_column=missing_rates,
        period_start=timestamps.min().isoformat(),
        period_end=timestamps.max().isoformat(),
    )


def load_phase9_dataset(path: str | Path) -> TrainingDataset:
    """Load one validated Phase-9 snapshot into the existing ML contract.

    Missing feature values are preserved here. Missing-value treatment belongs
    to the existing training/preprocessing pipeline and must not be silently
    performed by the provenance adapter.
    """
    source = Path(path)
    diagnostics = inspect_phase9_snapshot(source)
    frame = pd.read_parquet(source)

    # Reuse the validated feature order from the source schema.
    feature_columns = diagnostics.feature_columns
    return TrainingDataset(
        data=frame.copy(),
        feature_columns=feature_columns,
        label_column="label",
    )


def compare_snapshot_overlap(
    left: str | Path,
    right: str | Path,
) -> SnapshotOverlap:
    """Measure timestamp+symbol overlap without merging the snapshots."""
    left_path = Path(left)
    right_path = Path(right)

    left_frame = pd.read_parquet(left_path, columns=["timestamp", "symbol"])
    right_frame = pd.read_parquet(right_path, columns=["timestamp", "symbol"])

    left_keys = pd.MultiIndex.from_frame(left_frame.drop_duplicates())
    right_keys = pd.MultiIndex.from_frame(right_frame.drop_duplicates())
    overlapping = len(left_keys.intersection(right_keys))

    return SnapshotOverlap(
        left_path=str(left_path),
        right_path=str(right_path),
        overlapping_keys=int(overlapping),
    )


def validate_snapshot_set(paths: Iterable[str | Path]) -> tuple[SnapshotOverlap, ...]:
    """Validate each snapshot and report pairwise overlap.

    This function intentionally does not merge or choose snapshots. Selection
    remains an explicit caller decision.
    """
    normalized = tuple(Path(path) for path in paths)
    if not normalized:
        raise Phase9DatasetError("at least one Phase-9 snapshot is required")

    for path in normalized:
        inspect_phase9_snapshot(path)

    overlaps: list[SnapshotOverlap] = []
    for index, left in enumerate(normalized):
        for right in normalized[index + 1 :]:
            overlaps.append(compare_snapshot_overlap(left, right))
    return tuple(overlaps)
