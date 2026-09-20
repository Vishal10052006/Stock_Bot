"""AB-30 clean real market -> analysis integration.

Builds directly from existing Phase 4, Phase 5, and Phase 6 components.
No prediction, strategy, risk, or execution side effects occur here.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from intelligence.analysis.contracts import AnalysisContext
from intelligence.analysis.integration import build_analysis_context
from market.features.builder import build_features
from market.features.validation import validate_feature_dataset
from market.indicators.engine import IndicatorEngine
from market.regime.detector import detect_market_regime


class MarketAnalysisPipelineError(ValueError):
    """Raised when AB-30 cannot build a causal analysis snapshot."""


@dataclass(frozen=True, slots=True)
class MarketAnalysisResult:
    """Immutable result of the real Phase 4 -> 5 -> 6 -> Analysis path."""

    indicators: pd.DataFrame
    features: pd.DataFrame
    regime: pd.DataFrame
    analysis: AnalysisContext


def build_market_analysis(
    candles: pd.DataFrame,
    *,
    symbol: str,
    market_context: pd.DataFrame,
    sector_context: pd.DataFrame | None = None,
    sector_mappings: tuple = (),
    data_version: str = "market-v1",
    feature_version: str = "v1.0",
) -> MarketAnalysisResult:
    """Build one decision-time AnalysisContext from real market inputs."""
    if not isinstance(candles, pd.DataFrame):
        raise TypeError("candles must be a pandas DataFrame")
    if candles.empty:
        raise MarketAnalysisPipelineError("candles must not be empty")
    if not symbol.strip():
        raise MarketAnalysisPipelineError("symbol must not be empty")
    if not isinstance(market_context, pd.DataFrame):
        raise TypeError("market_context must be a pandas DataFrame")

    working = candles.copy()

    if "timestamp" not in working.columns:
        raise MarketAnalysisPipelineError("candles must contain timestamp")

    if "symbol" not in working.columns:
        working["symbol"] = symbol
    else:
        working["symbol"] = working["symbol"].fillna(symbol)

    timestamp = pd.to_datetime(working["timestamp"], utc=True)
    working["timestamp"] = timestamp
    working["symbol"] = working["symbol"].astype(str).str.upper()

    if working["symbol"].nunique() != 1:
        raise MarketAnalysisPipelineError(
            "AB-30 requires exactly one symbol per pipeline invocation"
        )

    working = working.sort_values("timestamp", kind="stable").reset_index(drop=True)

    # Existing Phase 4 calculation; no duplicate indicator implementation.
    indicators = IndicatorEngine().calculate(working)

    # Existing Phase 5 causal feature construction and validation.
    features = build_features(
        indicators,
        market_context=market_context,
        sector_context=sector_context,
        sector_mappings=sector_mappings,
    )
    features = validate_feature_dataset(features)

    required_regime = {
        "timestamp",
        "market_return_3",
        "market_return_12",
        "market_volatility_20",
    }

    missing = required_regime.difference(features.columns)
    if missing:
        raise MarketAnalysisPipelineError(
            "market context is insufficient for Phase 6 regime detection; "
            f"missing={sorted(missing)}"
        )

    # Existing Phase 6 causal regime detector.
    regime = detect_market_regime(
        features.loc[
            :,
            [
                "timestamp",
                "market_return_3",
                "market_return_12",
                "market_volatility_20",
            ],
        ]
    )

    # Existing AB-24 adapter turns validated Phase 5/6 output into AnalysisContext.
    analysis = build_analysis_context(
        features,
        regime_dataset=regime,
        data_version=data_version,
        feature_version=feature_version,
    )

    return MarketAnalysisResult(
        indicators=indicators,
        features=features,
        regime=regime,
        analysis=analysis,
    )
