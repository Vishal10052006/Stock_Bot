"""Phase-9 dataset provenance builder for Self-Learning.

This module binds the real Phase-9 snapshot adapter to the existing immutable
DatasetVersion contract. It deliberately does not select, merge, clean, or
mutate datasets.
"""

from __future__ import annotations

from pathlib import Path

from .contracts import DatasetVersion
from .dataset import build_dataset_version
from .real_dataset import load_phase9_dataset


def build_phase9_dataset_version(
    snapshot_path: str | Path,
    *,
    dataset_version: str,
    source: str,
    creation_timestamp: str,
    feature_schema_version: str,
    label_definition_version: str,
    known_limitations: tuple[str, ...] = (),
) -> DatasetVersion:
    """Build immutable provenance for one explicit Phase-9 snapshot.

    The snapshot is validated and loaded through the authoritative SL-21
    adapter before DatasetVersion metadata is constructed. No other snapshot
    is discovered, selected, concatenated, cleaned, or mutated.
    """
    path = Path(snapshot_path)
    if not str(dataset_version).strip():
        raise ValueError("dataset_version must not be empty")
    if not str(source).strip():
        raise ValueError("source must not be empty")
    if not str(creation_timestamp).strip():
        raise ValueError("creation_timestamp must not be empty")
    if not str(feature_schema_version).strip():
        raise ValueError("feature_schema_version must not be empty")
    if not str(label_definition_version).strip():
        raise ValueError("label_definition_version must not be empty")

    dataset = load_phase9_dataset(path)

    return build_dataset_version(
        dataset,
        dataset_version=dataset_version,
        source=source,
        creation_timestamp=creation_timestamp,
        feature_schema_version=feature_schema_version,
        label_definition_version=label_definition_version,
        known_limitations=known_limitations,
    )


__all__ = ["build_phase9_dataset_version"]
