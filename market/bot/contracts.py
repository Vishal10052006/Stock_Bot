"""Stable Market Bot contracts and boundary objects."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


MARKET_BOT_VERSION = "market-bot-v1.0"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class MarketContextMetadata:
    """Version/provenance metadata for one MarketContext."""

    market_version: str = MARKET_BOT_VERSION
    data_version: str = "unknown"
    feature_version: str = "unknown"
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("market_version", "data_version", "feature_version"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
        object.__setattr__(self, "market_version", self.market_version.strip())
        object.__setattr__(self, "data_version", self.data_version.strip())
        object.__setattr__(self, "feature_version", self.feature_version.strip())
        object.__setattr__(self, "provenance", dict(self.provenance))


@dataclass(frozen=True, slots=True)
class MarketState:
    """Descriptive state at a single causal timestamp.

    This object has no trading authority.
    """

    timestamp: datetime
    benchmark: str
    trend_state: str | None = None
    trend_strength: float | None = None
    range_state: str | None = None
    volatility_state: str | None = None
    volatility_level: float | None = None
    breadth_state: str | None = None
    sector_state: str | None = None
    rotation_state: str | None = None
    correlation_state: str | None = None
    liquidity_state: str | None = None
    strength_state: str | None = None
    strength_score: float | None = None
    regime: str | None = None
    regime_probability: float | None = None
    transition_state: str | None = None
    quality: float | None = None
    availability: str = "AVAILABLE"

    def __post_init__(self) -> None:
        _aware(self.timestamp)
        if not self.benchmark.strip():
            raise ValueError("benchmark must not be empty")
        if self.availability not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}:
            raise ValueError("invalid availability")
        for name in ("trend_strength", "regime_probability", "quality", "strength_score"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")
        object.__setattr__(self, "benchmark", self.benchmark.strip().upper())


@dataclass(frozen=True, slots=True)
class MarketContext:
    """Canonical Market Bot output consumed by downstream Analysis."""

    timestamp: datetime
    benchmark: str
    state: MarketState
    breadth: Mapping[str, Any] = field(default_factory=dict)
    sectors: Mapping[str, Any] = field(default_factory=dict)
    rotation: Mapping[str, Any] = field(default_factory=dict)
    correlation: Mapping[str, Any] = field(default_factory=dict)
    liquidity: Mapping[str, Any] = field(default_factory=dict)
    strength: Mapping[str, Any] = field(default_factory=dict)
    multi_timeframe: Mapping[str, Any] = field(default_factory=dict)
    metadata: MarketContextMetadata = field(default_factory=MarketContextMetadata)

    def __post_init__(self) -> None:
        _aware(self.timestamp)
        if self.timestamp != self.state.timestamp:
            raise ValueError("context timestamp must match state timestamp")
        if self.benchmark.strip().upper() != self.state.benchmark:
            raise ValueError("context benchmark must match state benchmark")
        for name in ("breadth", "sectors", "rotation", "correlation", "liquidity", "strength", "multi_timeframe"):
            object.__setattr__(self, name, dict(getattr(self, name)))
        object.__setattr__(self, "benchmark", self.benchmark.strip().upper())

    def to_mapping(self) -> dict[str, Any]:
        """Return a JSON-safe semantic mapping for AnalysisInput."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "benchmark": self.benchmark,
            "trend_state": self.state.trend_state,
            "trend_strength": self.state.trend_strength,
            "range_state": self.state.range_state,
            "volatility_state": self.state.volatility_state,
            "volatility_level": self.state.volatility_level,
            "breadth_state": self.state.breadth_state,
            "sector_state": self.state.sector_state,
            "rotation_state": self.state.rotation_state,
            "correlation_state": self.state.correlation_state,
            "liquidity_state": self.state.liquidity_state,
            "strength_state": self.state.strength_state,
            "strength_score": self.state.strength_score,
            "regime": self.state.regime,
            "regime_probability": self.state.regime_probability,
            "transition_state": self.state.transition_state,
            "quality": self.state.quality,
            "availability": self.state.availability,
            "breadth": self.breadth,
            "sectors": self.sectors,
            "rotation": self.rotation,
            "correlation": self.correlation,
            "liquidity": self.liquidity,
            "strength": self.strength,
            "multi_timeframe": self.multi_timeframe,
            "versions": {
                "market": self.metadata.market_version,
                "data": self.metadata.data_version,
                "features": self.metadata.feature_version,
            },
            "provenance": dict(self.metadata.provenance),
        }
