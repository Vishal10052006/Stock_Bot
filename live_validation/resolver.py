"""Resolve live predictions using the existing Phase 7 labeling contract.

The resolver never labels a prediction until its complete future horizon is
available. It uses the same candidate construction and tie-breaking semantics
as supervised training, preventing a second, subtly different live label rule.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math

import pandas as pd

from ml.labeling import LabelingConfig, label_decision
from ml.labeling.models import TradeCandidate as LabelingTradeCandidate
from trading.signals.models import CandidateConfig, CandidateDirection, TradeCandidate
from trading.signals.directional import build_directional_candidates
from trading.signals.labeling_adapter import to_labeling_candidate

from .models import LiveOutcome, LivePrediction, OutcomeStatus


class LiveOutcomeResolver:
    """Resolve stored live predictions once their Phase 7 horizon closes."""

    def __init__(
        self,
        *,
        labeling_config: LabelingConfig | None = None,
        candidate_config: CandidateConfig | None = None,
    ) -> None:
        self.labeling_config = labeling_config or LabelingConfig()
        self.candidate_config = candidate_config or CandidateConfig()

    def create_prediction(
        self,
        *,
        prediction_id: str,
        timestamp: pd.Timestamp,
        symbol: str,
        model_version: str,
        feature_version: str,
        dataset_version: str,
        probabilities: dict[str, float],
        generated_at: pd.Timestamp,
        decision_row: pd.Series,
    ) -> LivePrediction:
        """Snapshot causal candidate inputs alongside a model prediction."""
        if not isinstance(decision_row, pd.Series):
            raise TypeError("decision_row must be a pandas Series")

        long_candidate, short_candidate = build_directional_candidates(
            decision_row,
            config=self.candidate_config,
        )

        return LivePrediction(
            prediction_id=prediction_id,
            timestamp=timestamp,
            symbol=symbol,
            model_version=model_version,
            feature_version=feature_version,
            dataset_version=dataset_version,
            predicted_class=max(probabilities, key=probabilities.get),
            probabilities=probabilities,
            generated_at=generated_at,
            horizon_bars=self.labeling_config.horizon_bars,
            target_r_multiple=self.labeling_config.target_r_multiple,
            long_entry_price=long_candidate.entry_price,
            long_stop_price=long_candidate.stop_price,
            short_entry_price=short_candidate.entry_price,
            short_stop_price=short_candidate.stop_price,
        )

    def resolve(
        self,
        prediction: LivePrediction,
        candles: pd.DataFrame,
        *,
        resolved_at: datetime | pd.Timestamp | None = None,
    ) -> LiveOutcome:
        """Resolve one prediction or return PENDING while the horizon is open."""
        if not isinstance(prediction, LivePrediction):
            raise TypeError("prediction must be a LivePrediction")
        self._validate_candles(candles, prediction)

        future = candles.loc[
            (candles["symbol"].astype(str).str.upper() == prediction.symbol)
            & (candles["timestamp"] > prediction.timestamp)
        ].copy()
        future = future.sort_values("timestamp", kind="stable")

        if len(future) < prediction.horizon_bars:
            return LiveOutcome(
                prediction_id=prediction.prediction_id,
                status=OutcomeStatus.PENDING,
            )

        horizon_timestamps = future["timestamp"].iloc[: prediction.horizon_bars]
        cutoff = pd.Timestamp(horizon_timestamps.iloc[-1])

        usable = candles.loc[
            (candles["symbol"].astype(str).str.upper() == prediction.symbol)
            & (candles["timestamp"] <= cutoff)
        ].copy()
        usable = usable.sort_values("timestamp", kind="stable")

        long_candidate = LabelingTradeCandidate(
            timestamp=prediction.timestamp,
            symbol=prediction.symbol,
            direction=self._label_direction(CandidateDirection.LONG),
            entry_price=prediction.long_entry_price,
            stop_price=prediction.long_stop_price,
        )
        short_candidate = LabelingTradeCandidate(
            timestamp=prediction.timestamp,
            symbol=prediction.symbol,
            direction=self._label_direction(CandidateDirection.SHORT),
            entry_price=prediction.short_entry_price,
            stop_price=prediction.short_stop_price,
        )

        outcome = label_decision(
            candles=usable,
            long_candidate=long_candidate,
            short_candidate=short_candidate,
            config=self.labeling_config,
        )

        actual = outcome.label.value
        outcome_timestamp = pd.Timestamp(outcome.timestamp)
        observed_at = pd.Timestamp(resolved_at or datetime.now(timezone.utc))
        if observed_at.tzinfo is None:
            raise ValueError("resolved_at must be timezone-aware")
        if outcome_timestamp.tzinfo is None:
            raise ValueError("label outcome timestamp must be timezone-aware")

        outcome_bars = int(
            (
                future["timestamp"]
                .iloc[: prediction.horizon_bars]
                .le(outcome_timestamp)
            ).sum()
        )
        if outcome_bars <= 0:
            # NO_EDGE can legitimately be resolved at the end of the horizon.
            outcome_bars = prediction.horizon_bars

        return LiveOutcome(
            prediction_id=prediction.prediction_id,
            status=OutcomeStatus.RESOLVED,
            actual_class=actual,
            outcome_timestamp=outcome_timestamp,
            outcome_bars=outcome_bars,
            outcome_reason=self._outcome_reason(outcome),
            resolved_at=observed_at,
        )

    @staticmethod
    def _label_direction(direction: CandidateDirection):
        """Convert signal candidate direction into Phase 7 direction."""
        from ml.labeling.models import TradeDirection

        if direction is CandidateDirection.LONG:
            return TradeDirection.LONG
        if direction is CandidateDirection.SHORT:
            return TradeDirection.SHORT
        raise ValueError("direction must be LONG or SHORT")

    @staticmethod
    def _outcome_reason(outcome) -> str:
        """Return an auditable label reason without changing Phase 7 semantics."""
        return (
            f"long={outcome.long_outcome.outcome_reason};"
            f"short={outcome.short_outcome.outcome_reason}"
        )

    @staticmethod
    def _validate_candles(candles: pd.DataFrame, prediction: LivePrediction) -> None:
        required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
        if not isinstance(candles, pd.DataFrame):
            raise TypeError("candles must be a pandas DataFrame")
        missing = required.difference(candles.columns)
        if missing:
            raise ValueError(f"candles missing required columns: {sorted(missing)}")
        if candles.empty:
            raise ValueError("candles must not be empty")
        if not isinstance(candles["timestamp"].dtype, pd.DatetimeTZDtype):
            raise ValueError("candle timestamps must be timezone-aware")

        working = candles.copy()
        working["symbol"] = working["symbol"].astype(str).str.upper()
        working = working.sort_values(["symbol", "timestamp"], kind="stable")

        if working.duplicated(["symbol", "timestamp"]).any():
            raise ValueError("candles contain duplicate symbol/timestamp observations")
        if not working.groupby("symbol", sort=False)["timestamp"].apply(
            lambda values: values.is_monotonic_increasing
        ).all():
            raise ValueError("candles must be chronological within each symbol")
        if not math.isfinite(float(prediction.timestamp.value)):
            raise ValueError("prediction timestamp is invalid")
