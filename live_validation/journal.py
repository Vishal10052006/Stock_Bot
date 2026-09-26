"""Append-only JSONL persistence for live prediction-validation evidence."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import hashlib
from typing import Any

import pandas as pd

from .models import LiveOutcome, LivePrediction, OutcomeStatus


class LiveValidationJournal:
    """Persist predictions and their later outcomes in one append-only log."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @staticmethod
    def prediction_id(
        *,
        timestamp: pd.Timestamp,
        symbol: str,
        model_version: str,
    ) -> str:
        """Create a deterministic identity for one symbol/model/timestamp."""
        normalized = (
            f"{pd.Timestamp(timestamp).isoformat()}|"
            f"{str(symbol).strip().upper()}|"
            f"{str(model_version).strip()}"
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def append_prediction(self, prediction: LivePrediction) -> None:
        """Append one immutable prediction, rejecting duplicate identities."""
        if not isinstance(prediction, LivePrediction):
            raise TypeError("prediction must be a LivePrediction")
        records = self._read_events()
        if any(
            event.get("event_type") == "PREDICTION"
            and event.get("prediction_id") == prediction.prediction_id
            for event in records
        ):
            raise ValueError(
                f"prediction_id already exists: {prediction.prediction_id}"
            )

        payload = {
            "event_type": "PREDICTION",
            "prediction_id": prediction.prediction_id,
            "timestamp": pd.Timestamp(prediction.timestamp).isoformat(),
            "symbol": prediction.symbol,
            "model_version": prediction.model_version,
            "feature_version": prediction.feature_version,
            "dataset_version": prediction.dataset_version,
            "predicted_class": prediction.predicted_class,
            "probabilities": dict(prediction.probabilities),
            "generated_at": pd.Timestamp(prediction.generated_at).isoformat(),
            "horizon_bars": prediction.horizon_bars,
            "target_r_multiple": prediction.target_r_multiple,
            "long_entry_price": prediction.long_entry_price,
            "long_stop_price": prediction.long_stop_price,
            "short_entry_price": prediction.short_entry_price,
            "short_stop_price": prediction.short_stop_price,
        }
        self._append(payload)

    def append_outcome(self, outcome: LiveOutcome) -> None:
        """Append one resolved/pending outcome for an existing prediction."""
        if not isinstance(outcome, LiveOutcome):
            raise TypeError("outcome must be a LiveOutcome")
        events = self._read_events()
        prediction_exists = any(
            event.get("event_type") == "PREDICTION"
            and event.get("prediction_id") == outcome.prediction_id
            for event in events
        )
        if not prediction_exists:
            raise ValueError(
                f"cannot append outcome for unknown prediction_id: {outcome.prediction_id}"
            )

        if outcome.status is OutcomeStatus.RESOLVED:
            already_resolved = any(
                event.get("event_type") == "OUTCOME"
                and event.get("prediction_id") == outcome.prediction_id
                and event.get("status") == OutcomeStatus.RESOLVED.value
                for event in events
            )
            if already_resolved:
                raise ValueError(
                    f"prediction already has a resolved outcome: {outcome.prediction_id}"
                )

        payload: dict[str, Any] = {
            "event_type": "OUTCOME",
            "prediction_id": outcome.prediction_id,
            "status": outcome.status.value,
            "actual_class": outcome.actual_class,
            "outcome_timestamp": (
                pd.Timestamp(outcome.outcome_timestamp).isoformat()
                if outcome.outcome_timestamp is not None
                else None
            ),
            "outcome_bars": outcome.outcome_bars,
            "outcome_reason": outcome.outcome_reason,
            "resolved_at": (
                pd.Timestamp(outcome.resolved_at).isoformat()
                if outcome.resolved_at is not None
                else None
            ),
        }
        self._append(payload)

    def read_events(self) -> tuple[dict[str, Any], ...]:
        """Return all valid journal events in append order."""
        return tuple(self._read_events())

    def read_predictions(self) -> pd.DataFrame:
        """Return prediction observations as a normalized DataFrame."""
        rows = [
            event for event in self._read_events()
            if event.get("event_type") == "PREDICTION"
        ]
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame["generated_at"] = pd.to_datetime(frame["generated_at"], utc=True)
        return frame

    def read_latest_outcomes(self) -> dict[str, LiveOutcome]:
        """Return the latest outcome state for each prediction identity."""
        latest: dict[str, LiveOutcome] = {}
        for event in self._read_events():
            if event.get("event_type") != "OUTCOME":
                continue
            status = OutcomeStatus(str(event["status"]))
            if status is OutcomeStatus.PENDING:
                latest[event["prediction_id"]] = LiveOutcome(
                    prediction_id=event["prediction_id"],
                    status=OutcomeStatus.PENDING,
                )
                continue

            latest[event["prediction_id"]] = LiveOutcome(
                prediction_id=event["prediction_id"],
                status=OutcomeStatus.RESOLVED,
                actual_class=event["actual_class"],
                outcome_timestamp=pd.Timestamp(event["outcome_timestamp"]),
                outcome_bars=int(event["outcome_bars"]),
                outcome_reason=str(event["outcome_reason"]),
                resolved_at=pd.Timestamp(event["resolved_at"]),
            )
        return latest

    def _append(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(payload, sort_keys=True, separators=(",", ":"))
                + "\n"
            )

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in live validation journal at line {line_number}"
                ) from exc
            if not isinstance(value, dict):
                raise ValueError(
                    f"journal event at line {line_number} must be an object"
                )
            events.append(value)
        return events
