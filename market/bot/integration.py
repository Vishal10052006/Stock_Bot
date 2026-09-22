"""Adapters between MarketContext and the frozen Analysis Bot contract."""
from __future__ import annotations

from typing import Any

import pandas as pd

from intelligence.analysis.contracts import AnalysisInput
from market.data.context.market_context import build_context_returns
from .contracts import MarketContext


def market_context_for_analysis(context: MarketContext) -> dict[str, Any]:
    """Return the canonical mapping expected by AnalysisInput."""
    return context.to_mapping()


def build_analysis_input(
    *,
    timestamp: pd.Timestamp,
    symbol: str,
    features: dict[str, Any],
    market_context: MarketContext,
    sector_context: dict[str, Any] | None = None,
    regime: dict[str, Any] | None = None,
    research_context: Any | None = None,
    fundamental_context: Any | None = None,
    valuation_context: Any | None = None,
    data_version: str | None = None,
    feature_version: str | None = None,
) -> AnalysisInput:
    """Construct AnalysisInput without allowing future market context leakage."""
    analysis_timestamp = pd.Timestamp(timestamp)
    if analysis_timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    if market_context.timestamp > analysis_timestamp.to_pydatetime():
        raise ValueError("market context cannot be from the future of analysis timestamp")
    return AnalysisInput(
        timestamp=timestamp,
        symbol=symbol,
        features=features,
        market_context=market_context_for_analysis(market_context),
        sector_context=sector_context or {},
        regime=regime or {},
        research_context=research_context,
        fundamental_context=fundamental_context,
        valuation_context=valuation_context,
        data_version=data_version or market_context.metadata.data_version,
        feature_version=feature_version or market_context.metadata.feature_version,
    )


def build_phase5_market_context(
    benchmark_history: pd.DataFrame,
    *,
    market_context: MarketContext | None = None,
) -> pd.DataFrame:
    """Adapt benchmark history to the frozen Phase 5 market-context schema.

    The Phase 5/Analysis pipeline consumes a causal time series, not the
    immutable MarketContext snapshot. This adapter reuses the existing
    context-return builder and only renames its canonical fields; it does not
    duplicate regime detection or Analysis Bot logic.
    """
    if not isinstance(benchmark_history, pd.DataFrame):
        raise TypeError("benchmark_history must be a pandas DataFrame")

    context = build_context_returns(benchmark_history)
    context = context.rename(
        columns={
            "return_1": "market_return_1",
            "return_3": "market_return_3",
            "return_12": "market_return_12",
            "volatility_20": "market_volatility_20",
        }
    )

    ordered = [
        "timestamp",
        "market_return_1",
        "market_return_3",
        "market_return_12",
        "market_volatility_20",
    ]
    missing = set(ordered).difference(context.columns)
    if missing:
        raise ValueError(
            "phase 5 market context missing columns: "
            f"{sorted(missing)}"
        )

    if market_context is not None:
        latest = pd.Timestamp(context["timestamp"].iloc[-1])
        if latest != pd.Timestamp(market_context.timestamp):
            raise ValueError(
                "benchmark history endpoint does not match MarketContext timestamp"
            )

    return context.loc[:, ordered].copy()
