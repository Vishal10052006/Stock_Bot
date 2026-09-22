"""Causal point-in-time alignment for fundamental observations."""
from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from intelligence.analysis.fundamentals.contracts import FundamentalSnapshot


class FundamentalAlignmentError(ValueError):
    """Raised when fundamental observations cannot be causally aligned."""


def align_fundamental_snapshot(
    snapshots: Iterable[FundamentalSnapshot],
    *,
    symbol: str,
    decision_timestamp: pd.Timestamp,
) -> FundamentalSnapshot | None:
    """Select the latest observation available at the decision timestamp.

    The rule is strictly backward-looking: available_at must be <= decision
    timestamp. Future filings are never used and missing data stays missing.
    """
    decision = pd.Timestamp(decision_timestamp)
    if decision.tzinfo is None:
        raise FundamentalAlignmentError("decision_timestamp must be timezone-aware")
    normalized = symbol.strip().upper()
    candidates = [
        snapshot
        for snapshot in snapshots
        if snapshot.symbol == normalized and snapshot.available_at <= decision
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda snapshot: (snapshot.available_at, snapshot.period_end),
    )
