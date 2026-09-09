"""Feature engineering for the STOCK BOT trading system.

This module converts the causal outputs of the Phase 4 Indicator Engine
into an ML-ready FeatureDataset, including optional point-in-time market
and sector context.

Design principles:
    - Features must use only information available at the current row.
    - Relative features are preferred over raw price-level features.
    - Existing Phase 4 causal calculations are reused rather than
      reimplemented.
    - External market/sector context is aligned backward in time.
    - No future target/label information is introduced here.

References:
    ROADMAP_STOCK-BOT.pdf — Phase 5, Feature Engineering.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from market.data.context.enrichment import (
    CONTEXT_FEATURE_COLUMNS,
    enrich_market_sector_context,
)
from market.data.context.models import SectorMapping


# ---------------------------------------------------------------------------
# Public feature schema
# ---------------------------------------------------------------------------

FEATURE_COLUMNS: tuple[str, ...] = (
    # Trend.
    "price_ema_9_distance_pct",
    "price_ema_20_distance_pct",
    "price_ema_50_distance_pct",
    "ema_9_20_distance_pct",
    "ema_20_50_distance_pct",

    # Momentum.
    "rsi_14",
    "macd_histogram",
    "roc_14",

    # VWAP.
    "vwap_distance_pct",

    # Volatility.
    "atr_normalized",
    "bb_width_normalized",
    "realized_volatility_20",

    # Volume.
    "rvol_20",
    "volume_change_1",

    # Price structure.
    "distance_to_support_pct",
    "distance_to_resistance_pct",

    # Previous-day context.
    "previous_day_high_distance_pct",
    "previous_day_low_distance_pct",

    # Opening-range context.
    "opening_range_high_distance_pct",
    "opening_range_low_distance_pct",
    "opening_range_width_normalized",

    # Swing structure.
    "swing_high_distance_pct",
    "swing_low_distance_pct",

    # Retest structure.
    "retest_up",
    "retest_down",
    "retest_distance_pct",

    # Candle structure.
    "higher_high",
    "lower_low",
    "higher_low",
    "lower_high",

    # Market and sector context.
    *CONTEXT_FEATURE_COLUMNS,
)


# Columns that identify the observation but are not ML features.
IDENTIFIER_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "symbol",
)


def _validate_input(data: pd.DataFrame) -> None:
    """Validate the minimum Phase 4 feature-engineering schema."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")

    required = {
        "close",
        "ema_9",
        "ema_20",
        "ema_50",
        "rsi_14",
        "macd_histogram",
        "roc_14",
        "vwap_distance_pct",
        "atr_14",
        "bb_width",
        "realized_volatility_20",
        "rvol_20",
        "volume_change_1",
        "distance_to_support_pct",
        "distance_to_resistance_pct",
        "previous_day_high",
        "previous_day_low",
        "opening_range_high",
        "opening_range_low",
        "opening_range_width",
        "swing_high",
        "swing_low",
        "retest_up",
        "retest_down",
        "retest_distance_pct",
        "higher_high",
        "lower_low",
        "higher_low",
        "lower_high",
    }

    missing = required.difference(data.columns)

    if missing:
        raise ValueError(
            "missing required Phase 4 columns: "
            f"{sorted(missing)}"
        )

    if data.empty:
        raise ValueError("data must not be empty")

    if not pd.api.types.is_numeric_dtype(data["close"]):
        raise TypeError("close must contain numeric values")


def _relative_distance_pct(
    value: pd.Series,
    reference: pd.Series,
) -> pd.Series:
    """Calculate percentage distance from a reference value."""
    reference = reference.astype(float)
    safe_reference = reference.mask(reference == 0, np.nan)

    return (
        (value.astype(float) - safe_reference)
        .div(safe_reference)
        .mul(100.0)
    )


def build_features(
    data: pd.DataFrame,
    *,
    market_context: pd.DataFrame | None = None,
    sector_context: pd.DataFrame | None = None,
    sector_mappings: tuple[SectorMapping, ...] = (),
) -> pd.DataFrame:
    """Build FeatureDataset v1 from Phase 4 output.

    When market context is not supplied, context columns are retained as
    NaN so the frozen schema remains stable. Supplying market context adds
    causal index features; supplying sector context additionally requires
    point-in-time sector mappings.

    No learned scaler is applied here. Trainable preprocessing belongs in
    the later ML pipeline and must be fitted only on training data.
    """
    _validate_input(data)

    result = pd.DataFrame(index=data.index)

    for column in IDENTIFIER_COLUMNS:
        if column in data.columns:
            result[column] = data[column]

    # Trend.
    result["price_ema_9_distance_pct"] = _relative_distance_pct(
        data["close"], data["ema_9"]
    )
    result["price_ema_20_distance_pct"] = _relative_distance_pct(
        data["close"], data["ema_20"]
    )
    result["price_ema_50_distance_pct"] = _relative_distance_pct(
        data["close"], data["ema_50"]
    )
    result["ema_9_20_distance_pct"] = _relative_distance_pct(
        data["ema_9"], data["ema_20"]
    )
    result["ema_20_50_distance_pct"] = _relative_distance_pct(
        data["ema_20"], data["ema_50"]
    )

    # Momentum.
    result["rsi_14"] = data["rsi_14"].astype(float)
    result["macd_histogram"] = data["macd_histogram"].astype(float)
    result["roc_14"] = data["roc_14"].astype(float)

    # VWAP.
    result["vwap_distance_pct"] = data["vwap_distance_pct"].astype(float)

    # Volatility.
    result["atr_normalized"] = (
        data["atr_14"].astype(float)
        .div(data["close"].astype(float).replace(0, np.nan))
    )
    result["bb_width_normalized"] = (
        data["bb_width"].astype(float)
        .div(data["close"].astype(float).replace(0, np.nan))
    )
    result["realized_volatility_20"] = data[
        "realized_volatility_20"
    ].astype(float)

    # Volume.
    result["rvol_20"] = data["rvol_20"].astype(float)
    result["volume_change_1"] = data["volume_change_1"].astype(float)

    # Price structure.
    result["distance_to_support_pct"] = data[
        "distance_to_support_pct"
    ].astype(float)
    result["distance_to_resistance_pct"] = data[
        "distance_to_resistance_pct"
    ].astype(float)

    # Previous-day context.
    result["previous_day_high_distance_pct"] = _relative_distance_pct(
        data["close"], data["previous_day_high"]
    )
    result["previous_day_low_distance_pct"] = _relative_distance_pct(
        data["close"], data["previous_day_low"]
    )

    # Opening-range context.
    result["opening_range_high_distance_pct"] = _relative_distance_pct(
        data["close"], data["opening_range_high"]
    )
    result["opening_range_low_distance_pct"] = _relative_distance_pct(
        data["close"], data["opening_range_low"]
    )
    result["opening_range_width_normalized"] = (
        data["opening_range_width"].astype(float)
        .div(data["close"].astype(float).replace(0, np.nan))
    )

    # Swing structure.
    result["swing_high_distance_pct"] = _relative_distance_pct(
        data["close"], data["swing_high"]
    )
    result["swing_low_distance_pct"] = _relative_distance_pct(
        data["close"], data["swing_low"]
    )

    # Retest structure.
    result["retest_up"] = data["retest_up"]
    result["retest_down"] = data["retest_down"]
    result["retest_distance_pct"] = data[
        "retest_distance_pct"
    ].astype(float)

    # Candle structure.
    result["higher_high"] = data["higher_high"]
    result["lower_low"] = data["lower_low"]
    result["higher_low"] = data["higher_low"]
    result["lower_high"] = data["lower_high"]

    # Context is part of the frozen schema even when unavailable. This keeps
    # historical rows deterministic and allows missing external context to
    # remain explicitly missing rather than being fabricated.
    for column in CONTEXT_FEATURE_COLUMNS:
        result[column] = np.nan

    if market_context is not None:
        context = enrich_market_sector_context(
            data.loc[:, ["timestamp", "symbol", "close"]].copy(),
            market_context=market_context,
            sector_context=sector_context,
            sector_mappings=sector_mappings,
        )
        context = context.reindex(data.index)
        for column in CONTEXT_FEATURE_COLUMNS:
            result[column] = context[column]

    ordered_columns = [
        column
        for column in IDENTIFIER_COLUMNS
        if column in result.columns
    ] + list(FEATURE_COLUMNS)

    return result.loc[:, ordered_columns].copy()


class FeatureBuilder:
    """Object-oriented wrapper around the Phase 5 feature builder."""

    def build(
        self,
        data: pd.DataFrame,
        *,
        market_context: pd.DataFrame | None = None,
        sector_context: pd.DataFrame | None = None,
        sector_mappings: tuple[SectorMapping, ...] = (),
    ) -> pd.DataFrame:
        """Build FeatureDataset v1."""
        return build_features(
            data,
            market_context=market_context,
            sector_context=sector_context,
            sector_mappings=sector_mappings,
        )


# Frozen FeatureDataset contract version.
FEATURE_VERSION = "v1.0"
