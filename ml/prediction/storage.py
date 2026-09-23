"""Prediction telemetry storage contract.

The store is append-only and prediction-only. It records enough metadata to
trace a prediction back to the model, dataset, feature set, and generation
time. It does not persist trade actions or broker state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import pandas as pd


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    timestamp: pd.Timestamp
    symbol: str
    model_version: str
    dataset_version: str
    feature_version: str
    generated_at: pd.Timestamp
    prediction_type: str
    payload: dict[str, float | str | int | None]

    def __post_init__(self) -> None:
        for name in (
            "timestamp",
            "generated_at",
        ):
            value = pd.Timestamp(getattr(self, name))
            if value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        for name in (
            "symbol",
            "model_version",
            "dataset_version",
            "feature_version",
            "prediction_type",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dictionary")


class PredictionStore:
    """Append-only JSONL prediction telemetry store."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: PredictionRecord) -> None:
        if not isinstance(record, PredictionRecord):
            raise TypeError("record must be a PredictionRecord")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                **asdict(record),
                "timestamp": pd.Timestamp(record.timestamp).isoformat(),
                "generated_at": pd.Timestamp(record.generated_at).isoformat(),
            },
            sort_keys=True,
            default=str,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def read(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "symbol",
                    "model_version",
                    "dataset_version",
                    "feature_version",
                    "generated_at",
                    "prediction_type",
                    "payload",
                ]
            )
        rows = [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame["generated_at"] = pd.to_datetime(frame["generated_at"], utc=True)
        return frame
