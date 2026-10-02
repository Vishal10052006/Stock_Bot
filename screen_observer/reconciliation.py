"""S10 screen/market reconciliation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .contracts import VisualContext


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    status: str
    symbol_match: bool | None
    timeframe_match: bool | None
    age_seconds: float
    reasons: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return self.status == "MATCH"


def reconcile(
    context: VisualContext,
    *,
    market_symbol: str,
    market_timeframe: str,
    decision_timestamp: pd.Timestamp,
    max_age_seconds: float = 30.0,
) -> ReconciliationResult:
    decision_timestamp = pd.Timestamp(decision_timestamp)
    if decision_timestamp.tzinfo is None:
        raise ValueError("decision_timestamp must be timezone-aware")
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")

    market_symbol = market_symbol.strip().upper()
    market_timeframe = market_timeframe.strip().lower()
    age = (decision_timestamp - context.observed_at).total_seconds()
    reasons: list[str] = []

    if age < 0:
        reasons.append("SCREEN_OBSERVATION_FROM_FUTURE")
    elif age > max_age_seconds:
        reasons.append("SCREEN_OBSERVATION_STALE")

    symbol_match = None if context.symbol is None else context.symbol == market_symbol
    timeframe_match = (
        None if context.timeframe is None
        else context.timeframe.strip().lower() == market_timeframe
    )

    if symbol_match is False:
        reasons.append("SCREEN_SYMBOL_MISMATCH")
    if timeframe_match is False:
        reasons.append("SCREEN_TIMEFRAME_MISMATCH")
    if not context.chart_detected:
        reasons.append("SCREEN_CHART_NOT_DETECTED")
    if context.confidence.chart < 0.50:
        reasons.append("SCREEN_CHART_LOW_CONFIDENCE")

    status = "MATCH" if not reasons else "MISMATCH"
    return ReconciliationResult(
        status=status,
        symbol_match=symbol_match,
        timeframe_match=timeframe_match,
        age_seconds=age,
        reasons=tuple(reasons),
    )
