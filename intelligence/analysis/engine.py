"""Canonical Analysis Bot orchestration engine."""
from __future__ import annotations
from typing import Any

import pandas as pd

from intelligence.analysis.candidates import generate_candidates
from intelligence.analysis.contracts import AnalysisContext, AnalysisInput
from intelligence.analysis.market import analyze_market_context
from intelligence.analysis.provenance import build_provenance, feature_quality
from intelligence.analysis.relative import analyze_relative_performance
from intelligence.analysis.research import research_summary
from intelligence.analysis.sector import analyze_sector_context
from intelligence.analysis.structure import analyze_structure
from intelligence.analysis.technical import analyze_technical
from intelligence.analysis.volatility import analyze_volatility
from intelligence.analysis.volume import analyze_volume


class AnalysisEngine:
    """Compose existing causal analytical primitives into AnalysisContext."""

    def analyze(self, analysis_input: AnalysisInput) -> AnalysisContext:
        features = analysis_input.features
        technical = analyze_technical(features)
        structure = analyze_structure(features)
        volume = analyze_volume(features)
        volatility = analyze_volatility(features)
        market = analyze_market_context(analysis_input.market_context or features)
        sector = analyze_sector_context(analysis_input.sector_context or features)
        relative = analyze_relative_performance(features)
        research = research_summary(analysis_input.research_context)
        candidates = generate_candidates(technical, structure, volume, relative)
        direction = technical["direction"]
        if direction == "UNKNOWN" and structure.get("trend") in {"BULLISH", "BEARISH"}:
            direction = structure["trend"]
        state = technical["state"]
        if not market["available"] and not sector["available"] and direction == "UNKNOWN":
            state = "UNAVAILABLE"

        return AnalysisContext(
            timestamp=analysis_input.timestamp,
            symbol=analysis_input.symbol,
            technical_context=technical,
            structure_context=structure,
            volume_context=volume,
            volatility_context=volatility,
            market_context=market,
            sector_context=sector,
            relative_performance=relative,
            research_context=research,
            feature_vector=dict(features),
            analytical_direction=direction,
            analytical_state=state,
            candidates=candidates,
            quality=feature_quality(features),
            data_version=analysis_input.data_version,
            feature_version=analysis_input.feature_version,
            provenance=build_provenance(
                data_version=analysis_input.data_version,
                feature_version=analysis_input.feature_version,
                analysis_version="v1.0",
                sources={
                    "market_context": bool(analysis_input.market_context),
                    "sector_context": bool(analysis_input.sector_context),
                    "research_context": analysis_input.research_context is not None,
                },
            ),
        )


def analyze_latest_row(
    features: pd.DataFrame,
    *,
    regime: dict[str, Any] | None = None,
    market_context: dict[str, Any] | None = None,
    sector_context: dict[str, Any] | None = None,
    research_context: Any | None = None,
    data_version: str = "unknown",
    feature_version: str = "v1.0",
) -> AnalysisContext:
    """Analyze the latest row for one symbol without mutating input."""
    if not isinstance(features, pd.DataFrame):
        raise TypeError("features must be a pandas DataFrame")
    if features.empty:
        raise ValueError("features must not be empty")
    if "timestamp" not in features.columns or "symbol" not in features.columns:
        raise ValueError("features must contain timestamp and symbol")
    row = features.iloc[-1]
    timestamp = pd.Timestamp(row["timestamp"])
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    feature_values = {column: row[column] for column in features.columns if column not in {"timestamp", "symbol"}}
    return AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=timestamp,
            symbol=str(row["symbol"]),
            features=feature_values,
            regime=regime,
            market_context=market_context,
            sector_context=sector_context,
            research_context=research_context,
            data_version=data_version,
            feature_version=feature_version,
        )
    )
