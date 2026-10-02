"""Causal, observation-only cross-asset context."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

import pandas as pd

@dataclass(frozen=True, slots=True)
class CrossAssetRow:
    symbol: str
    timestamp: pd.Timestamp
    values: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        symbol = self.symbol.strip().upper()
        if not symbol: raise ValueError("symbol must not be empty")
        normalized = tuple(sorted((str(k), float(v)) for k, v in self.values))
        if len({k for k, _ in normalized}) != len(normalized): raise ValueError("duplicate cross-asset fields")
        if any(not math.isfinite(v) for _, v in normalized): raise ValueError("cross-asset values must be finite")
        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "values", normalized)

@dataclass(frozen=True, slots=True)
class CrossAssetContext:
    timestamp: pd.Timestamp
    rows: tuple[CrossAssetRow, ...]
    observed_count: int
    coverage: float
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        rows = tuple(self.rows)
        if self.observed_count != len(rows): raise ValueError("observed_count must match rows")
        if not 0 <= self.coverage <= 1: raise ValueError("coverage must be in [0, 1]")
        if any(row.timestamp > ts for row in rows): raise ValueError("future cross-asset observation rejected")
        symbols = [row.symbol for row in rows]
        if len(symbols) != len(set(symbols)): raise ValueError("duplicate cross-asset symbols")
        object.__setattr__(self, "timestamp", ts)

    def as_dict(self) -> dict[str, object]:
        return {"timestamp": self.timestamp.isoformat(), "rows": tuple({"symbol": r.symbol, "timestamp": r.timestamp.isoformat(), "values": dict(r.values)} for r in self.rows), "observed_count": self.observed_count, "coverage": self.coverage, "authority": self.authority}

def build_cross_asset_context(timestamp: pd.Timestamp, universe_symbols: tuple[str, ...] | list[str], observations: Mapping[str, Mapping[str, object]]) -> CrossAssetContext:
    timestamp = pd.Timestamp(timestamp)
    if timestamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
    universe = tuple(sorted({str(s).strip().upper() for s in universe_symbols if str(s).strip()}))
    if not universe: raise ValueError("universe_symbols must not be empty")
    rows = []
    for symbol, payload in observations.items():
        normalized = str(symbol).strip().upper()
        if normalized not in universe: raise ValueError("cross-asset symbol outside declared universe")
        if not isinstance(payload, Mapping): raise TypeError("cross-asset observation must be a mapping")
        if "timestamp" not in payload: raise ValueError("cross-asset observation missing timestamp")
        observed_at = pd.Timestamp(payload["timestamp"])
        if observed_at.tzinfo is None: raise ValueError("cross-asset observation timestamp must be timezone-aware")
        if observed_at > timestamp: raise ValueError("future cross-asset observation rejected")
        values = tuple((str(k), float(v)) for k, v in payload.items() if k != "timestamp")
        rows.append(CrossAssetRow(normalized, observed_at, values))
    rows.sort(key=lambda row: row.symbol)
    return CrossAssetContext(timestamp, tuple(rows), len(rows), len(rows) / len(universe))
