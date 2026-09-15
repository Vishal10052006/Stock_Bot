"""
Explicit adapter between the signal candidate layer and Phase 7.

The signal layer owns candidate construction.
The labeling layer owns future-outcome evaluation.

This module performs the domain-boundary conversion without allowing
the two layers to depend directly on each other's candidate model.
"""

from __future__ import annotations

from ml.labeling.models import (
    TradeCandidate as LabelingTradeCandidate,
    TradeDirection,
)

from .models import (
    CandidateDirection,
    TradeCandidate,
)


def to_labeling_candidate(
    candidate: TradeCandidate,
) -> LabelingTradeCandidate:
    """
    Convert a signal-layer TradeCandidate into the Phase 7 model.

    Only decision-time candidate fields cross this boundary.
    """

    if not isinstance(candidate, TradeCandidate):
        raise TypeError(
            "candidate must be a trading.signals TradeCandidate"
        )

    if candidate.direction == CandidateDirection.LONG:
        direction = TradeDirection.LONG
    elif candidate.direction == CandidateDirection.SHORT:
        direction = TradeDirection.SHORT
    else:
        raise ValueError(
            f"unsupported candidate direction: {candidate.direction}"
        )

    return LabelingTradeCandidate(
        timestamp=candidate.timestamp,
        symbol=candidate.symbol,
        direction=direction,
        entry_price=candidate.entry_price,
        stop_price=candidate.stop_price,
    )
