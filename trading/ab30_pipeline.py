"""AB-30 real Phase 4 -> Phase 5 -> Phase 6 integration helper.

This integration helper deliberately stops at AnalysisContext. It uses the
existing IndicatorEngine, FeatureBuilder/Validator, and MarketRegimeDetector.
Prediction/strategy/risk/execution remain downstream adapters already tested
by AB-25 through AB-29.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from intelligence.analysis.contracts import AnalysisContext
from intelligence.analysis.integration import build_analysis_context
from market.features.builder import build_features
from market.features.validation import validate_feature_dataset
from market.indicators.engine import IndicatorEngine
from market.regime.detector import detect_market_regime
from monitoring.runtime import MonitoringRuntime


class MarketAnalysisPipelineError(ValueError):
    """Raised when the real market-to-analysis pipeline cannot proceed."""


@dataclass(frozen=True, slots=True)
class MarketAnalysisResult:
    """Auditable result of the real market analytics path."""

    indicators: pd.DataFrame
    features: pd.DataFrame
    regime: pd.DataFrame
    analysis: AnalysisContext


def build_market_analysis(
    candles: pd.DataFrame,
    *,
    symbol: str,
    market_context: pd.DataFrame | None = None,
    sector_context: pd.DataFrame | None = None,
    sector_mappings: tuple = (),
    data_version: str = "market-v1",
    feature_version: str = "v1.0",
    monitoring: MonitoringRuntime | None = None,
) -> MarketAnalysisResult:
    """Run real Phase 4/5/6 components and produce one AnalysisContext.

    No future labels are accepted. The input candle frame is never mutated.
    """
    if not isinstance(candles, pd.DataFrame):
        raise TypeError("candles must be a pandas DataFrame")
    if candles.empty:
        raise MarketAnalysisPipelineError("candles must not be empty")
    if not symbol.strip():
        raise MarketAnalysisPipelineError("symbol must not be empty")

    working = candles.copy()
    if "timestamp" not in working.columns:
        raise MarketAnalysisPipelineError("candles must contain timestamp")
    if "symbol" not in working.columns:
        working["symbol"] = symbol
    else:
        working["symbol"] = working["symbol"].fillna(symbol)

    if not pd.api.types.is_datetime64_any_dtype(working["timestamp"]):
        working["timestamp"] = pd.to_datetime(
            working["timestamp"],
            utc=True,
        )
    elif working["timestamp"].dt.tz is None:
        working["timestamp"] = working["timestamp"].dt.tz_localize("UTC")

    working = working.sort_values("timestamp", kind="stable").reset_index(drop=True)
    working["symbol"] = working["symbol"].astype(str).str.upper()

    if working["symbol"].nunique() != 1:
        raise MarketAnalysisPipelineError(
            "AB-30 requires one symbol per pipeline invocation"
        )

    # Phase 6 regime detection requires point-in-time market context.
    # Fail closed before feature construction rather than allowing a
    # context-free feature frame to reach regime detection.
    if market_context is None:
        raise MarketAnalysisPipelineError(
            "AB-30 requires market context for Phase 6 regime detection; "
            "missing=['market_return_3', 'market_return_12', "
            "'market_volatility_20']"
        )

    indicators = IndicatorEngine().calculate(working)
    features = build_features(
        indicators,
        market_context=market_context,
        sector_context=sector_context,
        sector_mappings=sector_mappings,
    )
    features = validate_feature_dataset(features)

    regime_source = features.loc[
        :,
        ["timestamp"]
        + [
            column
            for column in (
                "market_return_3",
                "market_return_12",
                "market_volatility_20",
            )
            if column in features.columns
        ],
    ].copy()

    required_regime = {
        "timestamp",
        "market_return_3",
        "market_return_12",
        "market_volatility_20",
    }

    missing_regime = required_regime.difference(regime_source.columns)
    if missing_regime:
        raise MarketAnalysisPipelineError(
            "AB-30 requires market context for Phase 6 regime detection; "
            f"missing={sorted(missing_regime)}"
        )

    regime = detect_market_regime(regime_source)

    analysis = build_analysis_context(
        features,
        regime_dataset=regime,
        data_version=data_version,
        feature_version=feature_version,
        monitoring=monitoring,
    )

    return MarketAnalysisResult(
        indicators=indicators,
        features=features,
        regime=regime,
        analysis=analysis,
    )
