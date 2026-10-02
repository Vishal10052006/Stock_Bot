"""Market breadth aggregation for Module 6 M03."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from .contracts import StockIntelligence


@dataclass(frozen=True, slots=True)
class MarketBreadth:
    """Immutable descriptive breadth snapshot; never a trading decision."""

    timestamp: pd.Timestamp
    universe_count: int
    observed_count: int
    advances: int
    declines: int
    unchanged: int
    breadth_ratio: float | None
    advance_decline_ratio: float | None
    coverage: float
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        counts = (
            self.universe_count,
            self.observed_count,
            self.advances,
            self.declines,
            self.unchanged,
        )
        if any(value < 0 for value in counts):
            raise ValueError("breadth counts must be non-negative")
        if self.observed_count > self.universe_count:
            raise ValueError("observed_count cannot exceed universe_count")
        if self.advances + self.declines + self.unchanged != self.observed_count:
            raise ValueError("breadth counts must equal observed_count")
        if not 0.0 <= float(self.coverage) <= 1.0:
            raise ValueError("coverage must be in [0, 1]")
        if self.breadth_ratio is not None and not -1.0 <= float(self.breadth_ratio) <= 1.0:
            raise ValueError("breadth_ratio must be in [-1, 1]")
        if self.advance_decline_ratio is not None and float(self.advance_decline_ratio) < 0:
            raise ValueError("advance_decline_ratio must be non-negative")
        object.__setattr__(self, "timestamp", ts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "universe_count": self.universe_count,
            "observed_count": self.observed_count,
            "advances": self.advances,
            "declines": self.declines,
            "unchanged": self.unchanged,
            "breadth_ratio": self.breadth_ratio,
            "advance_decline_ratio": self.advance_decline_ratio,
            "coverage": self.coverage,
            "authority": self.authority,
        }


def build_market_breadth(
    *,
    timestamp: Any,
    universe_symbols: Iterable[str],
    observations: Iterable[StockIntelligence],
    return_key: str = "return_1",
) -> MarketBreadth:
    """Aggregate causal stock returns into advance/decline breadth.

    The return is read from each StockIntelligence analytical context. Missing
    returns are excluded from observed breadth rather than inferred. No
    threshold, signal, ranking, or position decision is created.
    """
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    symbols = tuple(sorted({str(symbol).strip().upper() for symbol in universe_symbols}))
    if any(not symbol for symbol in symbols):
        raise ValueError("universe_symbols must contain non-empty symbols")

    by_symbol: dict[str, StockIntelligence] = {}
    for observation in observations:
        if not isinstance(observation, StockIntelligence):
            raise TypeError("observations must contain StockIntelligence values")
        if observation.timestamp > ts:
            raise ValueError(f"future stock observation rejected: {observation.symbol}")
        if observation.symbol not in symbols:
            raise ValueError(f"stock observation outside universe: {observation.symbol}")
        if observation.symbol in by_symbol:
            raise ValueError(f"duplicate stock observation: {observation.symbol}")
        by_symbol[observation.symbol] = observation

    advances = declines = unchanged = 0
    for symbol in sorted(by_symbol):
        raw = by_symbol[symbol].analytical_context.get(return_key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid {return_key} for {symbol}") from exc
        if not pd.notna(value):
            continue
        if value > 0:
            advances += 1
        elif value < 0:
            declines += 1
        else:
            unchanged += 1

    observed = advances + declines + unchanged
    directional = advances + declines
    breadth_ratio = (
        (advances - declines) / directional if directional else None
    )
    ad_ratio = (
        advances / declines if declines else (float("inf") if advances else None)
    )
    return MarketBreadth(
        timestamp=ts,
        universe_count=len(symbols),
        observed_count=observed,
        advances=advances,
        declines=declines,
        unchanged=unchanged,
        breadth_ratio=breadth_ratio,
        advance_decline_ratio=ad_ratio,
        coverage=observed / len(symbols) if symbols else 0.0,
    )
