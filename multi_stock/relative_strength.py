"""Relative-strength aggregation for Module 6 M05."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from .contracts import StockIntelligence


@dataclass(frozen=True, slots=True)
class RelativeStrengthRow:
    """Descriptive stock-vs-benchmark return evidence."""

    symbol: str
    vs_market_1: float | None
    vs_sector_1: float | None

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        object.__setattr__(self, "symbol", symbol)
        for name in ("vs_market_1", "vs_sector_1"):
            value = getattr(self, name)
            if value is not None:
                value = float(value)
                if not pd.notna(value):
                    raise ValueError(f"{name} must be finite or None")
                object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class RelativeStrength:
    """Immutable point-in-time relative-strength snapshot."""

    timestamp: pd.Timestamp
    rows: tuple[RelativeStrengthRow, ...]
    observed_count: int
    coverage: float
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        symbols = tuple(row.symbol for row in self.rows)
        if symbols != tuple(sorted(symbols)) or len(symbols) != len(set(symbols)):
            raise ValueError("relative-strength rows must be sorted and unique")
        if self.observed_count != len(self.rows):
            raise ValueError("observed_count must equal row count")
        if not 0.0 <= float(self.coverage) <= 1.0:
            raise ValueError("coverage must be in [0, 1]")
        object.__setattr__(self, "timestamp", ts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "rows": [
                {
                    "symbol": row.symbol,
                    "vs_market_1": row.vs_market_1,
                    "vs_sector_1": row.vs_sector_1,
                }
                for row in self.rows
            ],
            "observed_count": self.observed_count,
            "coverage": self.coverage,
            "authority": self.authority,
        }


def build_relative_strength(
    *,
    timestamp: Any,
    universe_symbols: Iterable[str],
    observations: Iterable[StockIntelligence],
) -> RelativeStrength:
    """Expose existing causal stock-vs-market/sector return evidence.

    This module deliberately does not calculate a trading threshold or rank
    securities. It only reads relative-performance fields already produced by
    the causal market/sector enrichment layer.
    """
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    symbols = tuple(sorted({str(s).strip().upper() for s in universe_symbols}))
    if any(not s for s in symbols):
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

    rows: list[RelativeStrengthRow] = []
    for symbol in symbols:
        item = by_symbol.get(symbol)
        if item is None:
            continue
        context = item.analytical_context
        market = context.get("stock_vs_market_return_1")
        sector = context.get("stock_vs_sector_return_1")
        if market is None and sector is None:
            continue
        rows.append(
            RelativeStrengthRow(
                symbol=symbol,
                vs_market_1=None if market is None else float(market),
                vs_sector_1=None if sector is None else float(sector),
            )
        )

    return RelativeStrength(
        timestamp=ts,
        rows=tuple(rows),
        observed_count=len(rows),
        coverage=len(rows) / len(symbols) if symbols else 0.0,
    )
