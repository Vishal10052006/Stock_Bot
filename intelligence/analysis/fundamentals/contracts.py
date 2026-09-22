"""Immutable contracts for point-in-time fundamental data.

Fundamental observations are stored with both the financial reporting period
and the time the information became available to the trading system. The
available_at timestamp is the causal boundary used by alignment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any, Mapping

import pandas as pd

FUNDAMENTAL_VERSION = "fundamentals-v1.0"


class FundamentalContractError(ValueError):
    """Raised when a fundamental contract is invalid."""


def _aware(value: Any, name: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        raise FundamentalContractError(f"{name} must be timezone-aware")
    return ts


def _finite_mapping(values: Mapping[str, Any]) -> dict[str, float]:
    if not isinstance(values, Mapping):
        raise TypeError("metrics must be a mapping")
    result: dict[str, float] = {}
    for key, value in values.items():
        name = str(key).strip().lower()
        if not name:
            raise FundamentalContractError("metric names must not be empty")
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise FundamentalContractError(
                f"fundamental metric {name!r} must be numeric"
            ) from exc
        if not isfinite(number):
            raise FundamentalContractError(
                f"fundamental metric {name!r} must be finite"
            )
        result[name] = number
    return result


@dataclass(frozen=True, slots=True)
class FundamentalSnapshot:
    """One immutable, point-in-time financial observation for a symbol."""

    symbol: str
    period_start: pd.Timestamp
    period_end: pd.Timestamp
    published_at: pd.Timestamp
    available_at: pd.Timestamp
    metrics: Mapping[str, float] = field(default_factory=dict)
    currency: str = "INR"
    source: str = "unknown"
    source_version: str = "unknown"
    provenance: Mapping[str, Any] = field(default_factory=dict)
    statement_type: str = "unknown"
    consolidated: bool | None = None

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise FundamentalContractError("symbol must not be empty")
        period_start = _aware(self.period_start, "period_start")
        period_end = _aware(self.period_end, "period_end")
        published_at = _aware(self.published_at, "published_at")
        available_at = _aware(self.available_at, "available_at")
        if period_start > period_end:
            raise FundamentalContractError("period_start must be <= period_end")
        if published_at > available_at:
            raise FundamentalContractError(
                "published_at must be <= available_at"
            )
        if not self.currency or not self.source or not self.source_version:
            raise FundamentalContractError(
                "currency, source and source_version must be non-empty"
            )
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "period_start", period_start)
        object.__setattr__(self, "period_end", period_end)
        object.__setattr__(self, "published_at", published_at)
        object.__setattr__(self, "available_at", available_at)
        object.__setattr__(self, "metrics", _finite_mapping(self.metrics))
        object.__setattr__(self, "provenance", dict(self.provenance))

    def to_mapping(self) -> dict[str, Any]:
        """Return a JSON-safe representation suitable for AnalysisContext."""
        return {
            "symbol": self.symbol,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "published_at": self.published_at.isoformat(),
            "available_at": self.available_at.isoformat(),
            "metrics": dict(self.metrics),
            "currency": self.currency,
            "source": self.source,
            "source_version": self.source_version,
            "provenance": dict(self.provenance),
            "statement_type": self.statement_type,
            "consolidated": self.consolidated,
        }


@dataclass(frozen=True, slots=True)
class ValuationSnapshot:
    """Market-derived valuation facts aligned independently from statements."""

    symbol: str
    as_of: pd.Timestamp
    price: float
    market_cap: float | None = None
    enterprise_value: float | None = None
    earnings_ttm: float | None = None
    book_value: float | None = None
    ebitda_ttm: float | None = None
    free_cash_flow_ttm: float | None = None
    shares_outstanding: float | None = None
    source: str = "unknown"
    source_version: str = "unknown"

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        as_of = _aware(self.as_of, "as_of")
        if not symbol:
            raise FundamentalContractError("symbol must not be empty")
        numeric = {
            "price": self.price,
            "market_cap": self.market_cap,
            "enterprise_value": self.enterprise_value,
            "earnings_ttm": self.earnings_ttm,
            "book_value": self.book_value,
            "ebitda_ttm": self.ebitda_ttm,
            "free_cash_flow_ttm": self.free_cash_flow_ttm,
            "shares_outstanding": self.shares_outstanding,
        }
        for name, value in numeric.items():
            if value is not None and not isfinite(float(value)):
                raise FundamentalContractError(f"{name} must be finite")
        if float(self.price) < 0:
            raise FundamentalContractError("price must be >= 0")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "as_of", as_of)

    def ratios(self) -> dict[str, float | None]:
        """Compute valuation ratios only when their denominator is valid."""
        def ratio(numerator: float | None, denominator: float | None) -> float | None:
            if numerator is None or denominator is None or denominator == 0:
                return None
            return float(numerator) / float(denominator)

        return {
            "pe": ratio(self.market_cap, self.earnings_ttm),
            "pb": ratio(self.market_cap, self.book_value),
            "ev_ebitda": ratio(self.enterprise_value, self.ebitda_ttm),
            "fcf_yield": (
                None
                if self.market_cap in (None, 0) or self.free_cash_flow_ttm is None
                else float(self.free_cash_flow_ttm) / float(self.market_cap)
            ),
        }
