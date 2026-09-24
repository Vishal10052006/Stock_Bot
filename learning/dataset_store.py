"""Append-only dataset-version manifest storage for self-learning.

The learning engine stores metadata and provenance here. It never silently
rewrites a dataset used by a prior experiment.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from .self_learning_models import DatasetVersion


class DatasetManifestStore:
    """Append-only JSONL store for immutable dataset manifests."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, manifest: DatasetVersion) -> None:
        """Persist a manifest once per dataset_version."""
        if not isinstance(manifest, DatasetVersion):
            raise TypeError("manifest must be a DatasetVersion")

        for existing in self.read_all():
            if existing.dataset_version == manifest.dataset_version:
                if existing.fingerprint != manifest.fingerprint:
                    raise ValueError(
                        "dataset_version already exists with different metadata"
                    )
                return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dataset_version": manifest.dataset_version,
            "creation_timestamp": manifest.creation_timestamp,
            "source": manifest.source,
            "symbols": list(manifest.symbols),
            "period_start": manifest.period_start,
            "period_end": manifest.period_end,
            "row_count": manifest.row_count,
            "label_distribution": dict(manifest.label_distribution),
            "feature_schema_version": manifest.feature_schema_version,
            "label_definition_version": manifest.label_definition_version,
            "source_trade_ids": list(manifest.source_trade_ids),
            "known_limitations": list(manifest.known_limitations),
            "fingerprint": manifest.fingerprint,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")

    def read_all(self) -> tuple[DatasetVersion, ...]:
        """Load manifests and verify each stored fingerprint."""
        if not self.path.exists():
            return ()

        records: list[DatasetVersion] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise ValueError(f"blank dataset manifest line {line_number}")

            payload = json.loads(line)
            expected = payload.pop("fingerprint", None)
            manifest = DatasetVersion(
                dataset_version=str(payload["dataset_version"]),
                creation_timestamp=str(payload["creation_timestamp"]),
                source=str(payload["source"]),
                symbols=tuple(payload["symbols"]),
                period_start=str(payload["period_start"]),
                period_end=str(payload["period_end"]),
                row_count=int(payload["row_count"]),
                label_distribution={
                    str(key): int(value)
                    for key, value in payload["label_distribution"].items()
                },
                feature_schema_version=str(payload["feature_schema_version"]),
                label_definition_version=str(payload["label_definition_version"]),
                source_trade_ids=tuple(payload.get("source_trade_ids", ())),
                known_limitations=tuple(payload.get("known_limitations", ())),
            )
            if expected is not None and expected != manifest.fingerprint:
                raise ValueError(
                    f"dataset manifest fingerprint mismatch at line {line_number}"
                )
            records.append(manifest)

        return tuple(records)

    def get(self, dataset_version: str) -> DatasetVersion:
        """Return the exact manifest for a dataset version."""
        for manifest in self.read_all():
            if manifest.dataset_version == dataset_version:
                return manifest
        raise KeyError(f"unknown dataset_version: {dataset_version}")

    @staticmethod
    def new_version(prefix: str = "learning") -> str:
        """Create a timestamp-based version identifier without mutating storage."""
        now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{prefix}-{now}"
