"""Resolve live predictions using the existing Phase 7 labeling contract.

A prediction is never marked NO_EDGE merely because the live session has not
yet supplied the full future horizon. Resolution stays PENDING until the same
complete horizon required by Phase 7 is available.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math

import pandas as pd

from ml.labeling import LabelingConfig, label_decision
from ml.labeling.models import TradeCandidate as LabelingTradeCandidate, TradeDirection
from trading.signals.models import CandidateConfig
from trading.signals.directional import build_directional_candidates

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
        prediction_timestamp = pd.Timestamp(timestamp)
        row_timestamp = pd.Timestamp(decision_row.get("timestamp"))
        if prediction_timestamp.tzinfo is None or row_timestamp.tzinfo is None:
            raise ValueError(
                "prediction and decision-row timestamps must be timezone-aware"
            )
        if row_timestamp != prediction_timestamp:
            raise ValueError(
                "decision_row timestamp must match prediction timestamp"
            )
        if str(decision_row.get("symbol", symbol)).strip().upper() != str(symbol).strip().upper():
            raise ValueError("decision_row symbol must match prediction symbol")

        long_candidate, short_candidate = build_directional_candidates(
            decision_row,
            config=self.candidate_config,
        )

        return LivePrediction(
            prediction_id=prediction_id,
            timestamp=prediction_timestamp,
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

        working = candles.copy()
        working["symbol"] = working["symbol"].astype(str).str.strip().str.upper()
        future = working.loc[
            (working["symbol"] == prediction.symbol)
            & (working["timestamp"] > prediction.timestamp)
        ].sort_values("timestamp", kind="stable")

        if len(future) < prediction.horizon_bars:
            return LiveOutcome(
                prediction_id=prediction.prediction_id,
                status=OutcomeStatus.PENDING,
            )

        horizon = future.iloc[: prediction.horizon_bars]
        cutoff = pd.Timestamp(horizon.iloc[-1]["timestamp"])
        usable = working.loc[
            (working["symbol"] == prediction.symbol)
            & (working["timestamp"] <= cutoff)
        ].sort_values("timestamp", kind="stable")

        long_candidate = LabelingTradeCandidate(
            timestamp=prediction.timestamp,
            symbol=prediction.symbol,
            direction=TradeDirection.LONG,
            entry_price=prediction.long_entry_price,
            stop_price=prediction.long_stop_price,
        )
        short_candidate = LabelingTradeCandidate(
            timestamp=prediction.timestamp,
            symbol=prediction.symbol,
            direction=TradeDirection.SHORT,
            entry_price=prediction.short_entry_price,
            stop_price=prediction.short_stop_price,
        )

        outcome = label_decision(
            candles=usable,
            long_candidate=long_candidate,
            short_candidate=short_candidate,
            config=self.labeling_config,
        )

        observed_at = pd.Timestamp(
            resolved_at or datetime.now(timezone.utc)
        )
        if observed_at.tzinfo is None:
            raise ValueError("resolved_at must be timezone-aware")

        outcome_timestamp = outcome.outcome_timestamp
        if outcome_timestamp is None:
            outcome_timestamp = cutoff

        outcome_bars = outcome.outcome_bars
        if outcome_bars is None:
            outcome_bars = prediction.horizon_bars

        return LiveOutcome(
            prediction_id=prediction.prediction_id,
            status=OutcomeStatus.RESOLVED,
            actual_class=outcome.label.value,
            outcome_timestamp=pd.Timestamp(outcome_timestamp),
            outcome_bars=int(outcome_bars),
            outcome_reason=outcome.outcome_reason,
            resolved_at=observed_at,
        )

    @staticmethod
    def _validate_candles(
        candles: pd.DataFrame,
        prediction: LivePrediction,
    ) -> None:
        required = {
            "timestamp",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }
        if not isinstance(candles, pd.DataFrame):
            raise TypeError("candles must be a pandas DataFrame")
        missing = required.difference(candles.columns)
        if missing:
            raise ValueError(
                f"candles missing required columns: {sorted(missing)}"
            )
        if candles.empty:
            raise ValueError("candles must not be empty")
        if not isinstance(candles["timestamp"].dtype, pd.DatetimeTZDtype):
            raise ValueError("candle timestamps must be timezone-aware")

        working = candles.copy()
        working["symbol"] = working["symbol"].astype(str).str.strip().str.upper()
        working = working.sort_values(["symbol", "timestamp"], kind="stable")

        if working.duplicated(["symbol", "timestamp"]).any():
            raise ValueError(
                "candles contain duplicate symbol/timestamp observations"
            )
        if not working.groupby("symbol", sort=False)["timestamp"].apply(
            lambda values: values.is_monotonic_increasing
        ).all():
            raise ValueError("candles must be chronological within each symbol")

        numeric = working[
            ["open", "high", "low", "close", "volume"]
        ].to_numpy(dtype=float)
        if not np.isfinite(numeric).all():
            raise ValueError("candles contain non-finite numeric values")
        if (working[["open", "high", "low", "close"]] <= 0).any().any():
            raise ValueError("candles contain non-positive OHLC values")
        if (working["volume"] < 0).any():
            raise ValueError("candles contain negative volume")
