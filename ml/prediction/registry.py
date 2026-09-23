"""File-backed Prediction Bot model registry.

The registry records reproducibility and lifecycle metadata.  It does not
promote a model into production or authorize trading.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from ml.model_registry import ModelRegistryRecord


class PredictionModelRegistry:
    """Small deterministic JSON registry for research model artifacts."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("registry root must be an object")
        return data

    def register(self, record: ModelRegistryRecord) -> None:
        """Insert or replace one model version by exact model_version."""
        if not isinstance(record, ModelRegistryRecord):
            raise TypeError("record must be a ModelRegistryRecord")
        records = self._read()
        records[record.model_version] = asdict(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(records, sort_keys=True, indent=2, default=str),
            encoding="utf-8",
        )

    def get(self, model_version: str) -> ModelRegistryRecord:
        """Return one registered model version."""
        records = self._read()
        if model_version not in records:
            raise KeyError(f"model_version not registered: {model_version}")
        return ModelRegistryRecord(**records[model_version])

    def list_versions(self) -> tuple[str, ...]:
        """Return registered model versions in deterministic order."""
        return tuple(sorted(self._read()))

    def set_status(self, model_version: str, status: str) -> None:
        """Update lifecycle metadata without changing model bytes."""
        record = self.get(model_version)
        updated = ModelRegistryRecord(
            model_version=record.model_version,
            model_family=record.model_family,
            feature_version=record.feature_version,
            dataset_version=record.dataset_version,
            code_version=record.code_version,
            target_version=record.target_version,
            training_period_start=record.training_period_start,
            training_period_end=record.training_period_end,
            validation_period_start=record.validation_period_start,
            validation_period_end=record.validation_period_end,
            test_period_start=record.test_period_start,
            test_period_end=record.test_period_end,
            hyperparameters=record.hyperparameters,
            metrics=record.metrics,
            approval_status=status,
        )
        self.register(updated)
