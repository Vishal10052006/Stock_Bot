"""S10/S14 screen-to-market reconciliation.

S14 hardens identity and temporal causality checks. The market feed remains
authoritative; screen evidence can only become usable contextual evidence when
identity and freshness checks pass.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .contracts import VisualContext
from .timeframe import normalize_timeframe


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
    """Reconcile screen identity/freshness against authoritative market context.

    Freshness is inclusive at the configured boundary: age == max_age_seconds
    is usable. Any future observation, stale observation, missing identity,
    invalid timeframe, or explicit identity mismatch fails closed.
    """

    decision_timestamp = pd.Timestamp(decision_timestamp)
    if decision_timestamp.tzinfo is None:
        raise ValueError("decision_timestamp must be timezone-aware")
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")

    market_symbol = market_symbol.strip().upper()
    market_timeframe = market_timeframe.strip()
    reasons: list[str] = []

    if not market_symbol:
        reasons.append("MARKET_SYMBOL_INVALID")
    if not market_timeframe:
        reasons.append("MARKET_TIMEFRAME_INVALID")

    normalized_market_timeframe = normalize_timeframe(market_timeframe)
    if market_timeframe and normalized_market_timeframe is None:
        reasons.append("MARKET_TIMEFRAME_INVALID")

    observed_at = pd.Timestamp(context.observed_at)
    age = (decision_timestamp - observed_at).total_seconds()

    if age < 0:
        reasons.append("SCREEN_OBSERVATION_FROM_FUTURE")
    elif age > max_age_seconds:
        reasons.append("SCREEN_OBSERVATION_STALE")

    screen_symbol = (
        context.symbol.strip().upper() if context.symbol is not None else None
    )
    screen_timeframe = (
        normalize_timeframe(context.timeframe)
        if context.timeframe is not None
        else None
    )

    symbol_match = None if screen_symbol is None else screen_symbol == market_symbol
    timeframe_match = (
        None
        if context.timeframe is None
        else screen_timeframe is not None
        and normalized_market_timeframe is not None
        and screen_timeframe == normalized_market_timeframe
    )

    if screen_symbol is None or not screen_symbol:
        reasons.append("SCREEN_SYMBOL_MISSING")
    elif symbol_match is False:
        reasons.append("SCREEN_SYMBOL_MISMATCH")

    if context.timeframe is None or not context.timeframe.strip():
        reasons.append("SCREEN_TIMEFRAME_MISSING")
    elif screen_timeframe is None:
        reasons.append("SCREEN_TIMEFRAME_INVALID")
    elif timeframe_match is False:
        reasons.append("SCREEN_TIMEFRAME_MISMATCH")

    status = "MATCH" if not reasons else "MISMATCH"
    return ReconciliationResult(
        status=status,
        symbol_match=symbol_match,
        timeframe_match=timeframe_match,
        age_seconds=age,
        reasons=tuple(reasons),
    )
