"""Adapters between MarketContext and the frozen Analysis Bot contract."""
from __future__ import annotations

from typing import Any

import pandas as pd

from intelligence.analysis.contracts import AnalysisInput
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
    """Construct AnalysisInput without changing Analysis Bot code."""
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
