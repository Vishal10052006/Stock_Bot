"""Deterministic descriptive stock ranking for Module 6 M01."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .contracts import StockIntelligence


@dataclass(frozen=True, slots=True)
class StockRank:
    """One informational stock rank; never a trade instruction."""

    rank: int
    symbol: str
    score: float
    source: str = "quality"

    def __post_init__(self) -> None:
        if self.rank <= 0:
            raise ValueError("rank must be positive")
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        if not 0.0 <= float(self.score) <= 1.0:
            raise ValueError("score must be in [0, 1]")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "source", self.source.strip())


@dataclass(frozen=True, slots=True)
class StockRanking:
    """Immutable deterministic ranking snapshot."""

    timestamp: Any
    ranks: tuple[StockRank, ...]
    excluded_symbols: tuple[str, ...] = ()
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        import pandas as pd

        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        symbols = tuple(item.symbol for item in self.ranks)
        if len(symbols) != len(set(symbols)):
            raise ValueError("ranks must not contain duplicate symbols")
        expected = tuple(range(1, len(self.ranks) + 1))
        if tuple(item.rank for item in self.ranks) != expected:
            raise ValueError("ranks must be contiguous starting at 1")
        excluded = tuple(symbol.strip().upper() for symbol in self.excluded_symbols)
        if len(excluded) != len(set(excluded)):
            raise ValueError("excluded_symbols must be unique")
        if set(symbols) & set(excluded):
            raise ValueError("symbol cannot be both ranked and excluded")
        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(self, "excluded_symbols", tuple(sorted(excluded)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "ranks": [
                {
                    "rank": item.rank,
                    "symbol": item.symbol,
                    "score": item.score,
                    "source": item.source,
                }
                for item in self.ranks
            ],
            "excluded_symbols": list(self.excluded_symbols),
            "authority": self.authority,
        }


def rank_stocks(
    *,
    timestamp: Any,
    observations: Iterable[StockIntelligence],
) -> StockRanking:
    """Rank available stock contexts by their existing quality score.

    This consumes an upstream analytical quality field; it does not create
    a trading signal, threshold, position size, or risk decision.
    """
    import pandas as pd

    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    items = tuple(observations)
    seen: set[str] = set()
    eligible: list[StockIntelligence] = []
    excluded: list[str] = []

    for item in items:
        if item.timestamp > ts:
            raise ValueError(f"future stock observation rejected: {item.symbol}")
        if item.symbol in seen:
            raise ValueError(f"duplicate stock observation: {item.symbol}")
        seen.add(item.symbol)
        if item.quality is None:
            excluded.append(item.symbol)
        else:
            eligible.append(item)

    ordered = sorted(
        eligible,
        key=lambda item: (-float(item.quality), item.symbol),
    )
    ranks = tuple(
        StockRank(rank=index, symbol=item.symbol, score=float(item.quality))
        for index, item in enumerate(ordered, start=1)
    )
    return StockRanking(
        timestamp=ts,
        ranks=ranks,
        excluded_symbols=tuple(sorted(excluded)),
    )
