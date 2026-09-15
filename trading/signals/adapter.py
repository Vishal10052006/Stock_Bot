"""
Adapter from Phase 8 strategy decisions to research candidates.

NO_TRADE decisions never become TradeCandidates.
"""

from __future__ import annotations

import pandas as pd

from trading.strategy.models import StrategyDecision, StrategyDirection

from .candidate import build_candidate
from .models import CandidateConfig, CandidateDirection, TradeCandidate


def build_candidate_from_decision(
    decision: StrategyDecision,
    row: pd.Series,
    *,
    config: CandidateConfig | None = None,
) -> TradeCandidate | None:
    """
    Convert a Phase 8 StrategyDecision into a research candidate.

    NO_TRADE produces no candidate.
    LONG and SHORT require causal decision-time market data.
    """

    if not isinstance(decision, StrategyDecision):
        raise TypeError(
            "decision must be a StrategyDecision"
        )

    if not isinstance(row, pd.Series):
        raise TypeError(
            "row must be a pandas Series"
        )

    if "timestamp" not in row.index:
        raise ValueError(
            "candidate input row is missing timestamp"
        )

    if "symbol" not in row.index:
        raise ValueError(
            "candidate input row is missing symbol"
        )

    row_timestamp = pd.Timestamp(row["timestamp"])

    if row_timestamp.tzinfo is None:
        raise ValueError(
            "candidate input row timestamp must be timezone-aware"
        )

    decision_timestamp = pd.Timestamp(decision.timestamp)

    if decision_timestamp != row_timestamp:
        raise ValueError(
            "strategy decision timestamp does not match "
            "candidate input row timestamp"
        )

    row_symbol = str(row["symbol"]).strip()

    if row_symbol != decision.symbol:
        raise ValueError(
            "strategy decision symbol does not match "
            "candidate input row symbol"
        )

    if decision.direction == StrategyDirection.NO_TRADE:
        return None

    if decision.direction == StrategyDirection.LONG:
        direction = CandidateDirection.LONG
    elif decision.direction == StrategyDirection.SHORT:
        direction = CandidateDirection.SHORT
    else:
        raise ValueError(
            f"unsupported strategy direction: {decision.direction}"
        )

    return build_candidate(
        row,
        direction,
        config=config,
    )
