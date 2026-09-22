"""Typed contracts for the STOCK_BOT Analysis Bot.

The Analysis Bot consumes validated decision-time observations and emits an
immutable, versioned analytical context. It never emits an order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

import numpy as np
import pandas as pd

ANALYSIS_VERSION = "v1.0"
FEATURE_CONTEXT_VERSION = "v1.0"
SUPPORTED_DIRECTIONS = frozenset({"BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN"})
SUPPORTED_STATES = frozenset({"ALIGNED", "CONFLICT", "NEUTRAL", "UNAVAILABLE"})


class AnalysisContractError(ValueError):
    """Raised when an Analysis Bot contract is invalid."""


def _require_aware_timestamp(value: Any, name: str) -> pd.Timestamp:
    """Return a timezone-aware pandas timestamp."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise AnalysisContractError(f"{name} must be timezone-aware")
    return timestamp


def _sanitize_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Copy a context mapping while preserving missing values."""
    return dict(value or {})

def _dashboard_safe(value: Any) -> Any:
    """Convert common pandas/NumPy values into dashboard-safe primitives."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.generic):
        return _dashboard_safe(value.item())
    if isinstance(value, Mapping):
        return {str(key): _dashboard_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_dashboard_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


@dataclass(frozen=True, slots=True)
class AnalysisInput:
    """Validated boundary object entering the Analysis Bot."""

    timestamp: pd.Timestamp
    symbol: str
    features: Mapping[str, Any]
    regime: Mapping[str, Any] | None = None
    market_context: Mapping[str, Any] | None = None
    sector_context: Mapping[str, Any] | None = None
    research_context: Any | None = None
    fundamental_context: Any | None = None
    valuation_context: Any | None = None
    data_version: str = "unknown"
    feature_version: str = FEATURE_CONTEXT_VERSION

    def __post_init__(self) -> None:
        timestamp = _require_aware_timestamp(self.timestamp, "timestamp")
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise AnalysisContractError("symbol must not be empty")
        if not isinstance(self.features, Mapping):
            raise TypeError("features must be a mapping")
        if not self.data_version:
            raise AnalysisContractError("data_version must not be empty")
        if not self.feature_version:
            raise AnalysisContractError("feature_version must not be empty")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", symbol)
        # Freeze the boundary by copying mutable mappings into owned dicts.
        for field_name in (
            "technical_context",
            "structure_context",
            "volume_context",
            "volatility_context",
            "market_context",
            "sector_context",
            "relative_performance",
            "research_context",
            "feature_vector",
            "quality",
            "provenance",
            "fundamental_context",
            "valuation_context",
        ):
            object.__setattr__(
                self,
                field_name,
                _sanitize_mapping(getattr(self, field_name)),
            )
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "features", _sanitize_mapping(self.features))
        object.__setattr__(self, "regime", _sanitize_mapping(self.regime))
        object.__setattr__(self, "market_context", _sanitize_mapping(self.market_context))
        object.__setattr__(self, "sector_context", _sanitize_mapping(self.sector_context))


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Canonical Analysis Bot output consumed by downstream components."""

    timestamp: pd.Timestamp
    symbol: str
    technical_context: Mapping[str, Any]
    structure_context: Mapping[str, Any]
    volume_context: Mapping[str, Any]
    volatility_context: Mapping[str, Any]
    market_context: Mapping[str, Any]
    sector_context: Mapping[str, Any]
    relative_performance: Mapping[str, Any]
    research_context: Mapping[str, Any]
    feature_vector: Mapping[str, Any]
    analytical_direction: str = "UNKNOWN"
    analytical_state: str = "UNAVAILABLE"
    candidates: tuple[str, ...] = ()
    quality: Mapping[str, Any] = field(default_factory=dict)
    analysis_version: str = ANALYSIS_VERSION
    feature_version: str = FEATURE_CONTEXT_VERSION
    data_version: str = "unknown"
    provenance: Mapping[str, Any] = field(default_factory=dict)
    fundamental_context: Mapping[str, Any] = field(default_factory=dict)
    valuation_context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        timestamp = _require_aware_timestamp(self.timestamp, "timestamp")
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise AnalysisContractError("symbol must not be empty")
        if self.analytical_direction not in SUPPORTED_DIRECTIONS:
            raise AnalysisContractError(f"unsupported analytical_direction: {self.analytical_direction}")
        if self.analytical_state not in SUPPORTED_STATES:
            raise AnalysisContractError(f"unsupported analytical_state: {self.analytical_state}")
        if not self.analysis_version or not self.feature_version or not self.data_version:
            raise AnalysisContractError("version fields must be non-empty")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", symbol)

    def to_dashboard_payload(self) -> dict[str, Any]:
        """Return a stable, JSON-safe dashboard/context payload."""
        return _dashboard_safe(
            {
                "symbol": self.symbol,
                "timestamp": self.timestamp,
                "direction": self.analytical_direction,
                "state": self.analytical_state,
                "candidates": self.candidates,
                "technical": self.technical_context,
                "structure": self.structure_context,
                "volume": self.volume_context,
                "volatility": self.volatility_context,
                "market": self.market_context,
                "sector": self.sector_context,
                "relative_performance": self.relative_performance,
                "research": self.research_context,
                "fundamentals": self.fundamental_context,
                "valuation": self.valuation_context,
                "quality": self.quality,
                "versions": {
                    "analysis": self.analysis_version,
                    "features": self.feature_version,
                    "data": self.data_version,
                },
                "provenance": self.provenance,
            }
        )


def dataframe_to_feature_mapping(row: pd.Series) -> dict[str, Any]:
    """Convert one feature row into JSON-safe scalar values."""
    result: dict[str, Any] = {}
    for column, value in row.items():
        if value is None or value is pd.NA:
            result[column] = None
            continue
        if isinstance(value, (pd.Timestamp, datetime)):
            result[column] = pd.Timestamp(value).isoformat()
            continue
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and np.isnan(value):
            result[column] = None
        else:
            result[column] = value
    return result
