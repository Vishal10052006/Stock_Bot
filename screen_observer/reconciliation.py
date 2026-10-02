"""Screen/market reconciliation (S10).

The market feed remains authoritative for structured market values. Screen
observations are contextual evidence and are never allowed to overwrite the
market data contract.
"""

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
    age = (decision_timestamp - context.observed_at).total_seconds()

    reasons: list[str] = []
    symbol_match = context.symbol is None or context.symbol == market_symbol.upper()
    timeframe_match = (
        context.timeframe is None
        or context.timeframe.lower() == market_timeframe.lower()
    )

    if age < 0:
        reasons.append("SCREEN_OBSERVATION_FROM_FUTURE")
    elif age > max_age_seconds:
        reasons.append("SCREEN_OBSERVATION_STALE")

    if not symbol_match:
        reasons.append("SCREEN_SYMBOL_MISMATCH")
    if not timeframe_match:
        reasons.append("SCREEN_TIMEFRAME_MISMATCH")

    status = "MATCH" if not reasons else "MISMATCH"
    return ReconciliationResult(
        status=status,
        symbol_match=symbol_match,
        timeframe_match=timeframe_match,
        age_seconds=age,
        reasons=tuple(reasons),
    )
