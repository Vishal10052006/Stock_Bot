"""Production composition of Market Bot context with the frozen AB-30 path.

This module is an orchestration boundary only. Market Bot owns market-state
construction, while AB-30 remains the authority for Phase 4 -> Phase 5 ->
Phase 6 -> Analysis. No regime or feature logic is duplicated here.
"""
from __future__ import annotations

from dataclasses import replace

import pandas as pd

from market.bot.contracts import MarketContext
from market.bot.integration import build_phase5_market_context
from market.bot.provenance import build_provenance
from trading.ab30_pipeline import MarketAnalysisResult, build_market_analysis


def build_market_analysis_from_market_bot(
    candles: pd.DataFrame,
    *,
    symbol: str,
    benchmark_history: pd.DataFrame,
    market_context: MarketContext,
    sector_context: pd.DataFrame | None = None,
    sector_mappings: tuple = (),
    data_version: str | None = None,
    feature_version: str | None = None,
) -> MarketAnalysisResult:
    """Run the production Market Bot -> AB-30 composition.

    ``market_context`` is the immutable Market Bot snapshot. Its timestamp
    must match the endpoint of ``benchmark_history``; the adapter converts
    the history into the causal Phase 5 schema. AB-30 then performs the
    existing Phase 4 -> Phase 5 -> Phase 6 -> Analysis path unchanged.

    Market Bot provenance is attached to the resulting AnalysisContext by
    this composition boundary; the frozen Analysis Bot implementation is
    not modified.
    """
    phase5_market_context = build_phase5_market_context(
        benchmark_history,
        market_context=market_context,
    )

    result = build_market_analysis(
        candles,
        symbol=symbol,
        market_context=phase5_market_context,
        sector_context=sector_context,
        sector_mappings=sector_mappings,
        data_version=data_version or market_context.metadata.data_version,
        feature_version=feature_version or market_context.metadata.feature_version,
    )

    provenance = dict(result.analysis.provenance)
    provenance["market_bot"] = build_provenance(market_context)
    analysis = replace(result.analysis, provenance=provenance)
    return replace(result, analysis=analysis)
