"""Strategy -> TradeCandidate boundary.

This adapter keeps candidate construction in trading.signals while making
the Strategy Engine decision the authority for materializing a candidate.
"""

from __future__ import annotations

import pandas as pd

from trading.signals.candidate import build_candidate
from trading.signals.models import CandidateConfig, CandidateDirection, TradeCandidate
from trading.signals.validation import validate_candidate

from .models import StrategyDecision, StrategyDirection


def build_candidate_from_strategy(
    decision: StrategyDecision,
    row: pd.Series,
    *,
    config: CandidateConfig | None = None,
) -> TradeCandidate:
    """Materialize a causal TradeCandidate from an approved strategy direction.

    The row must contain only decision-time information. The adapter never
    reads future labels or outcome columns.
    """
    if not isinstance(decision, StrategyDecision):
        raise TypeError("decision must be a StrategyDecision")

    if not isinstance(row, pd.Series):
        raise TypeError("row must be a pandas Series")

    if decision.direction is StrategyDirection.NO_TRADE:
        raise ValueError(
            "NO_TRADE decisions cannot produce TradeCandidate"
        )

    row_timestamp = pd.Timestamp(row.get("timestamp"))
    if row_timestamp.tzinfo is None:
        raise ValueError(
            "candidate row timestamp must be timezone-aware"
        )

    if row_timestamp != decision.timestamp:
        raise ValueError(
            "candidate row timestamp must match strategy timestamp"
        )

    row_symbol = str(row.get("symbol", "")).strip().upper()
    if row_symbol != decision.symbol:
        raise ValueError(
            "candidate row symbol must match strategy symbol"
        )

    direction = (
        CandidateDirection.LONG
        if decision.direction is StrategyDirection.LONG
        else CandidateDirection.SHORT
    )

    candidate = build_candidate(
        row,
        direction,
        config=config,
    )
    validate_candidate(candidate)

    return candidate
