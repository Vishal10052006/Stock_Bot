"""AB-24 adapter from validated FeatureDataset/Regime outputs to AnalysisContext.

This module is the integration seam between existing Phase 5/6 contracts and
the Analysis Bot. It performs no new indicator or feature calculation.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from intelligence.analysis.contracts import AnalysisContext, AnalysisInput
from intelligence.analysis.engine import AnalysisEngine
from market.features.validation import validate_feature_dataset


class AnalysisIntegrationError(ValueError):
    """Raised when upstream analytical datasets cannot be integrated."""


def build_analysis_context(
    feature_dataset: pd.DataFrame,
    *,
    regime_dataset: pd.DataFrame | None = None,
    research_context: Any | None = None,
    data_version: str = "unknown",
    feature_version: str = "v1.0",
    analysis_engine: AnalysisEngine | None = None,
) -> AnalysisContext:
    """Build AnalysisContext from a validated real FeatureDataset row.

    The caller is responsible for providing PIT-aligned market/sector context
    already present in FeatureDataset v1. Regime is attached by exact
    decision timestamp and is therefore never forward-filled.
    """
    validated = validate_feature_dataset(feature_dataset)

    if validated["symbol"].nunique() != 1:
        raise AnalysisIntegrationError(
            "AB-24 currently requires exactly one symbol per analysis call"
        )

    row = validated.iloc[-1]
    timestamp = pd.Timestamp(row["timestamp"])
    symbol = str(row["symbol"])

    regime_context: dict[str, Any] = {}
    if regime_dataset is not None:
        if not isinstance(regime_dataset, pd.DataFrame):
            raise TypeError("regime_dataset must be a pandas DataFrame")
        required = {"timestamp", "regime", "regime_probability"}
        missing = required.difference(regime_dataset.columns)
        if missing:
            raise AnalysisIntegrationError(
                f"regime_dataset missing columns: {sorted(missing)}"
            )
        matches = regime_dataset.loc[
            regime_dataset["timestamp"].eq(timestamp)
        ]
        if not matches.empty:
            regime_row = matches.iloc[-1]
            regime_context = {
                "regime": regime_row["regime"],
                "regime_probability": regime_row["regime_probability"],
            }

    features: dict[str, Any] = {}
    for column in validated.columns:
        if column not in {"timestamp", "symbol"}:
            value = row[column]
            if value is pd.NA or pd.isna(value):
                features[column] = None
            else:
                features[column] = value

    context_map = {
        key: features.get(key)
        for key in (
            "market_return_1",
            "market_return_3",
            "market_return_12",
            "market_volatility_20",
            "sector_return_1",
            "sector_return_3",
            "sector_return_12",
            "sector_volatility_20",
        )
    }

    engine = analysis_engine or AnalysisEngine()
    return engine.analyze(
        AnalysisInput(
            timestamp=timestamp,
            symbol=symbol,
            features=features,
            regime=regime_context,
            market_context=context_map,
            sector_context=context_map,
            research_context=research_context,
            data_version=data_version,
            feature_version=feature_version,
        )
    )
