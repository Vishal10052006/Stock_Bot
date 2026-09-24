"""Immutable dataset-version adapter for Self-Learning.

A dataset version is provenance metadata, not a mutable copy of the ML data.
The actual TrainingDataset remains owned by ml.datasets.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any

import pandas as pd

from ml.datasets.models import TrainingDataset
from .contracts import DatasetVersion


def dataframe_fingerprint(frame: pd.DataFrame) -> str:
    """Return a deterministic SHA-256 identity for a tabular dataset."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    normalized = frame.copy()
    normalized = normalized.sort_index(axis=1)
    payload = {
        "columns": [str(column) for column in normalized.columns],
        "dtypes": [str(dtype) for dtype in normalized.dtypes],
        "rows": normalized.to_dict(orient="records"),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_dataset_version(
    dataset: TrainingDataset,
    *,
    dataset_version: str,
    source: str,
    creation_timestamp: str,
    feature_schema_version: str,
    label_definition_version: str,
    known_limitations: tuple[str, ...] = (),
) -> DatasetVersion:
    """Create immutable provenance metadata from the authoritative dataset."""
    if not isinstance(dataset, TrainingDataset):
        raise TypeError("dataset must be a TrainingDataset")

    symbols = tuple(
        sorted(
            {
                str(symbol)
                for symbol in dataset.data["symbol"].dropna().unique()
            }
        )
    )
    if not symbols:
        raise ValueError("dataset must contain at least one symbol")

    timestamps = pd.to_datetime(dataset.data["timestamp"], utc=False)
    if timestamps.empty:
        raise ValueError("dataset must contain observations")

    distribution = Counter(
        str(label) for label in dataset.data[dataset.label_column]
    )

    return DatasetVersion(
        dataset_version=dataset_version,
        source=source,
        creation_timestamp=creation_timestamp,
        symbols=symbols,
        period_start=timestamps.min().isoformat(),
        period_end=timestamps.max().isoformat(),
        row_count=len(dataset.data),
        label_distribution=dict(sorted(distribution.items())),
        feature_schema_version=feature_schema_version,
        label_definition_version=label_definition_version,
        source_fingerprints=(dataframe_fingerprint(dataset.data),),
        known_limitations=known_limitations,
    )
