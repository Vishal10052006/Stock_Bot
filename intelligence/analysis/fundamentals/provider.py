"""Provider boundary for fundamental observations.

No external credentials or vendor SDK are embedded here. Human-operated
providers can implement this protocol and return normalized snapshots.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

import pandas as pd

from intelligence.analysis.fundamentals.contracts import FundamentalSnapshot


class FundamentalProvider(Protocol):
    """Minimal provider contract for normalized point-in-time fundamentals."""

    def snapshots(self, symbol: str) -> Iterable[FundamentalSnapshot]:
        """Return historical observations for one symbol."""


class InMemoryFundamentalProvider:
    """Deterministic reference provider useful for tests and local validation."""

    def __init__(self, snapshots: Iterable[FundamentalSnapshot] = ()) -> None:
        self._snapshots = tuple(snapshots)

    def snapshots(self, symbol: str) -> tuple[FundamentalSnapshot, ...]:
        normalized = symbol.strip().upper()
        return tuple(
            snapshot for snapshot in self._snapshots if snapshot.symbol == normalized
        )
