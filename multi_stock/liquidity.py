"""Liquidity context aggregation for Module 6 M06."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
import pandas as pd


@dataclass(frozen=True, slots=True)
class LiquiditySnapshot:
    """Immutable descriptive point-in-time liquidity snapshot."""
    timestamp: pd.Timestamp
    symbols: tuple[str, ...]
    traded_value: Mapping[str, float | None]
    observed_count: int
    coverage: float
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        symbols = tuple(s.strip().upper() for s in self.symbols)
        if symbols != tuple(sorted(symbols)) or len(symbols) != len(set(symbols)):
            raise ValueError("symbols must be sorted and unique")
        if set(self.traded_value) != set(symbols):
            raise ValueError("traded_value keys must match symbols")
        if self.observed_count != sum(v is not None for v in self.traded_value.values()):
            raise ValueError("observed_count must match available liquidity")
        if not 0.0 <= float(self.coverage) <= 1.0:
            raise ValueError("coverage must be in [0, 1]")
        for symbol, value in self.traded_value.items():
            if value is not None and (not pd.notna(float(value)) or float(value) < 0):
                raise ValueError(f"invalid traded value for {symbol}")
        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "traded_value", dict(self.traded_value))

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbols": list(self.symbols),
            "traded_value": dict(self.traded_value),
            "observed_count": self.observed_count,
            "coverage": self.coverage,
            "authority": self.authority,
        }


def build_liquidity_snapshot(
    *,
    timestamp: Any,
    universe_symbols: tuple[str, ...] | list[str],
    measurements: Mapping[str, Any],
) -> LiquiditySnapshot:
    """Expose explicit PIT liquidity measurements without reselecting a universe."""
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    symbols = tuple(sorted({str(s).strip().upper() for s in universe_symbols}))
    if any(not s for s in symbols):
        raise ValueError("universe_symbols must contain non-empty symbols")

    values: dict[str, float | None] = {symbol: None for symbol in symbols}
    for raw_symbol, measurement in measurements.items():
        symbol = str(raw_symbol).strip().upper()
        if symbol not in values:
            raise ValueError(f"liquidity measurement outside universe: {symbol}")
        if not hasattr(measurement, "as_of") or not hasattr(measurement, "average_traded_value"):
            raise TypeError("measurements must expose as_of and average_traded_value")
        as_of = pd.Timestamp(measurement.as_of)
        if as_of.tzinfo is not None:
            as_of = as_of.tz_convert(ts.tz)
        if as_of.date() > ts.date():
            raise ValueError(f"future liquidity measurement rejected: {symbol}")
        raw_value = measurement.average_traded_value
        values[symbol] = None if raw_value is None else float(raw_value)

    observed = sum(value is not None for value in values.values())
    return LiquiditySnapshot(
        timestamp=ts,
        symbols=symbols,
        traded_value=values,
        observed_count=observed,
        coverage=observed / len(symbols) if symbols else 0.0,
    )
