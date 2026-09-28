"""Fail-closed Prediction Bot failure contracts.

Failures are explicit observability events. They never become a trade decision,
and the handler never fabricates a prediction from missing or invalid inputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import pandas as pd


@dataclass(frozen=True, slots=True)
class PredictionFailure:
    """Immutable record describing a rejected prediction request."""

    timestamp: pd.Timestamp
    symbol: str
    code: str
    message: str
    model_version: str
    feature_version: str
    dataset_version: str

    def __post_init__(self) -> None:
        if pd.Timestamp(self.timestamp).tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        for name in ("symbol", "code", "message", "model_version", "feature_version", "dataset_version"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")


class PredictionFailureStore:
    """Append-only JSONL store for rejected prediction requests."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, failure: PredictionFailure) -> None:
        if not isinstance(failure, PredictionFailure):
            raise TypeError("failure must be a PredictionFailure")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(failure)
        payload["timestamp"] = pd.Timestamp(failure.timestamp).isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def read(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(
                columns=[
                    "timestamp", "symbol", "code", "message",
                    "model_version", "feature_version", "dataset_version",
                ]
            )
        rows = [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        return frame
