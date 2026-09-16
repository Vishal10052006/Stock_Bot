"""
Causal construction of both directional research candidates.

This module exists for Phase 7/9 target generation.

Unlike the Phase 8 strategy adapter, it does not decide whether
a trade should be taken. It constructs the hypothetical LONG and
SHORT candidates from the same decision-time market row so that
Phase 7 can determine the three-class outcome:

    LONG_SUCCESS
    SHORT_SUCCESS
    NO_EDGE

No future candles are accessed here.
"""

from __future__ import annotations

import pandas as pd

from .candidate import build_candidate
from .models import (
    CandidateConfig,
    CandidateDirection,
    TradeCandidate,
)


def build_directional_candidates(
    row: pd.Series,
    *,
    config: CandidateConfig | None = None,
) -> tuple[TradeCandidate, TradeCandidate]:
    """
    Build both LONG and SHORT candidates from one decision-time row.

    Parameters
    ----------
    row:
        One decision-time market/indicator row.

    config:
        Explicit candidate/stop configuration.

    Returns
    -------
    tuple[TradeCandidate, TradeCandidate]
        ``(long_candidate, short_candidate)``.

    Notes
    -----
    This function intentionally does not consult Phase 8 strategy
    decisions. Its purpose is target construction for supervised
    learning, not trade selection.

    Only information available at ``row["timestamp"]`` is used.
    """

    if not isinstance(row, pd.Series):
        raise TypeError("row must be a pandas Series")

    long_candidate = build_candidate(
        row,
        CandidateDirection.LONG,
        config=config,
    )

    short_candidate = build_candidate(
        row,
        CandidateDirection.SHORT,
        config=config,
    )

    if long_candidate.timestamp != short_candidate.timestamp:
        raise ValueError(
            "LONG and SHORT candidates must have the same timestamp"
        )

    if long_candidate.symbol != short_candidate.symbol:
        raise ValueError(
            "LONG and SHORT candidates must have the same symbol"
        )

    return long_candidate, short_candidate
