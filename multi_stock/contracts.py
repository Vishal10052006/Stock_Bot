"""Immutable contracts for multi-stock descriptive intelligence."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping
import pandas as pd

def _aware(value: Any, name: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return ts

@dataclass(frozen=True, slots=True)
class StockIntelligence:
    timestamp: pd.Timestamp
    symbol: str
    state: str
    direction: str
    quality: float | None
    analytical_context: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _aware(self.timestamp, "timestamp"))
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        object.__setattr__(self, "symbol", symbol)
        if self.quality is not None and not 0.0 <= float(self.quality) <= 1.0:
            raise ValueError("quality must be in [0, 1]")
        object.__setattr__(self, "analytical_context", dict(self.analytical_context))
        object.__setattr__(self, "provenance", dict(self.provenance))

@dataclass(frozen=True, slots=True)
class MultiStockObservation:
    timestamp: pd.Timestamp
    symbols: tuple[str, ...]
    observations: tuple[StockIntelligence, ...]
    available_count: int
    unavailable_count: int
    direction_counts: Mapping[str, int]
    state_counts: Mapping[str, int]
    coverage: float
    universe_version: str
    data_version: str
    provenance: Mapping[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _aware(self.timestamp, "timestamp"))
        normalized = tuple(s.strip().upper() for s in self.symbols)
        if any(not s for s in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("symbols must be unique and non-empty")
        if tuple(sorted(normalized)) != normalized:
            raise ValueError("symbols must be sorted")
        if self.available_count < 0 or self.unavailable_count < 0:
            raise ValueError("counts must be non-negative")
        if self.available_count + self.unavailable_count != len(normalized):
            raise ValueError("counts must equal universe size")
        if not 0.0 <= float(self.coverage) <= 1.0:
            raise ValueError("coverage must be in [0, 1]")
        if not self.universe_version.strip() or not self.data_version.strip():
            raise ValueError("version fields must not be empty")
        object.__setattr__(self, "symbols", normalized)
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "direction_counts", dict(self.direction_counts))
        object.__setattr__(self, "state_counts", dict(self.state_counts))
        object.__setattr__(self, "provenance", dict(self.provenance))
    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbols": list(self.symbols),
            "available_count": self.available_count,
            "unavailable_count": self.unavailable_count,
            "direction_counts": dict(self.direction_counts),
            "state_counts": dict(self.state_counts),
            "coverage": self.coverage,
            "universe_version": self.universe_version,
            "data_version": self.data_version,
            "provenance": dict(self.provenance),
            "observations": [
                {"timestamp": x.timestamp.isoformat(), "symbol": x.symbol,
                 "state": x.state, "direction": x.direction, "quality": x.quality,
                 "analytical_context": dict(x.analytical_context),
                 "provenance": dict(x.provenance)}
                for x in self.observations
            ],
        }

@dataclass(frozen=True, slots=True)
class MultiStockContext:
    timestamp: pd.Timestamp
    universe_symbols: tuple[str, ...]
    observation: MultiStockObservation
    market_context: Mapping[str, Any] = field(default_factory=dict)
    sector_context: Mapping[str, Any] = field(default_factory=dict)
    authority: str = "OBSERVATION_ONLY"
    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _aware(self.timestamp, "timestamp"))
        if self.observation.timestamp != self.timestamp:
            raise ValueError("observation timestamp must match context timestamp")
        normalized = tuple(s.strip().upper() for s in self.universe_symbols)
        if tuple(sorted(normalized)) != normalized or len(normalized) != len(set(normalized)):
            raise ValueError("universe_symbols must be sorted and unique")
        if normalized != self.observation.symbols:
            raise ValueError("universe_symbols must match observation symbols")
        object.__setattr__(self, "universe_symbols", normalized)
        object.__setattr__(self, "market_context", dict(self.market_context))
        object.__setattr__(self, "sector_context", dict(self.sector_context))
    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "universe_symbols": list(self.universe_symbols),
            "observation": self.observation.as_dict(),
            "market_context": dict(self.market_context),
            "sector_context": dict(self.sector_context),
            "authority": self.authority,
        }
