"""Observation-only screen reviewer for live-paper sessions.

The reviewer compares desktop visual evidence with the authoritative market
runtime. It can flag identity, timeframe, freshness, confidence, and capture
errors, but it cannot change Strategy, Risk, Safety, or Execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from screen_observer.contracts import VisualContext
from screen_observer.reconciliation import ReconciliationResult, reconcile


@dataclass(frozen=True, slots=True)
class ScreenReview:
    status: str
    severity: str
    observed_at: pd.Timestamp
    decision_timestamp: pd.Timestamp
    symbol: str | None
    timeframe: str | None
    confidence: float
    reasons: tuple[str, ...]
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        observed = pd.Timestamp(self.observed_at)
        decision = pd.Timestamp(self.decision_timestamp)
        if observed.tzinfo is None or decision.tzinfo is None:
            raise ValueError("review timestamps must be timezone-aware")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("review confidence must be in [0, 1]")
        if self.authority != "OBSERVATION_ONLY":
            raise ValueError("screen reviewer cannot have trading authority")
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "decision_timestamp", decision)
        object.__setattr__(self, "reasons", tuple(self.reasons))

    @property
    def usable(self) -> bool:
        return self.status == "MATCH"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "severity": self.severity,
            "observed_at": self.observed_at.isoformat(),
            "decision_timestamp": self.decision_timestamp.isoformat(),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }


class ScreenReviewer:
    """Evaluate one screen observation against authoritative runtime context."""

    def __init__(self, *, max_age_seconds: float = 30.0, min_confidence: float = 0.70):
        if max_age_seconds < 0:
            raise ValueError("max_age_seconds must be non-negative")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0, 1]")
        self.max_age_seconds = float(max_age_seconds)
        self.min_confidence = float(min_confidence)

    def review(
        self,
        context: VisualContext,
        *,
        market_symbol: str,
        market_timeframe: str,
        decision_timestamp: pd.Timestamp,
    ) -> ScreenReview:
        if not isinstance(context, VisualContext):
            raise TypeError("context must be VisualContext")

        result: ReconciliationResult = reconcile(
            context,
            market_symbol=market_symbol,
            market_timeframe=market_timeframe,
            decision_timestamp=decision_timestamp,
            max_age_seconds=self.max_age_seconds,
        )
        confidence = float(context.confidence.overall)
        reasons = list(result.reasons)

        if confidence < self.min_confidence:
            reasons.append("SCREEN_CONFIDENCE_LOW")

        if not reasons:
            status, severity = "MATCH", "INFO"
        elif "SCREEN_OBSERVATION_FROM_FUTURE" in reasons:
            status, severity = "MISMATCH", "CRITICAL"
        elif (
            "SCREEN_SYMBOL_MISMATCH" in reasons
            or "SCREEN_TIMEFRAME_MISMATCH" in reasons
        ):
            status, severity = "MISMATCH", "HIGH"
        elif "SCREEN_OBSERVATION_STALE" in reasons or "SCREEN_CONFIDENCE_LOW" in reasons:
            status, severity = "DEGRADED", "WARNING"
        else:
            status, severity = "MISMATCH", "HIGH"

        return ScreenReview(
            status=status,
            severity=severity,
            observed_at=context.observed_at,
            decision_timestamp=pd.Timestamp(decision_timestamp),
            symbol=context.symbol,
            timeframe=context.timeframe,
            confidence=confidence,
            reasons=tuple(dict.fromkeys(reasons)),
        )


__all__ = ["ScreenReview", "ScreenReviewer"]
