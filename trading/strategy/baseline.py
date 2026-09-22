"""
Phase 8 — Deterministic Baseline Strategy.

The strategy consumes only decision-time features and the Phase 6
market regime. It never accesses future candles or Phase 7 labels.

Baseline V1:

LONG:
    TREND_UP
    + price above VWAP
    + sufficient RVOL
    + higher-high structure
    + higher-low structure

SHORT:
    TREND_DOWN
    + price below VWAP
    + sufficient RVOL
    + lower-low structure
    + lower-high structure

Everything else:
    NO_TRADE
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from market.regime.models import MarketRegime

from .models import (
    BaselineStrategyConfig,
    NoTradeReason,
    StrategyDecision,
    StrategyDirection,
)


_REQUIRED_COLUMNS = {
    "timestamp",
    "symbol",
    "regime",
    "regime_probability",
    "vwap_distance_pct",
    "rvol_20",
    "higher_high",
    "higher_low",
    "lower_low",
    "lower_high",
}


def _validate_row(row: pd.Series) -> None:
    """Validate the decision-time inputs before strategy evaluation."""

    missing = _REQUIRED_COLUMNS.difference(row.index)

    if missing:
        raise ValueError(
            f"strategy input is missing required columns: {sorted(missing)}"
        )

    # Numeric decision-time features must be present and finite.
    for column in (
        "regime_probability",
        "vwap_distance_pct",
        "rvol_20",
    ):
        value = row[column]

        if pd.isna(value):
            raise ValueError(
                f"{column} must not be missing"
            )

        if not math.isfinite(float(value)):
            raise ValueError(
                f"{column} must be finite"
            )

    # Structure flags are nullable boolean decision-time features.
    # Missing structure information must never become a trade signal.
    structure_columns = (
        "higher_high",
        "higher_low",
        "lower_low",
        "lower_high",
    )

    for column in structure_columns:
        value = row[column]

        if pd.isna(value):
            raise ValueError(
                f"{column} must not be missing"
            )

        if not isinstance(value, (bool, np.bool_)):
            raise ValueError(
                f"{column} must be boolean"
            )


def _decision(
    row: pd.Series,
    direction: StrategyDirection,
    rationale: str,
    config: BaselineStrategyConfig,
    primary_reason: NoTradeReason | None = None,
) -> StrategyDecision:
    """Construct an auditable strategy decision."""

    if direction is StrategyDirection.NO_TRADE and primary_reason is None:
        primary_reason = NoTradeReason.STRATEGY_CONDITION_FAILED

    return StrategyDecision(
        timestamp=pd.Timestamp(row["timestamp"]),
        symbol=str(row["symbol"]),
        direction=direction,
        strategy_version=config.strategy_version,
        rationale=rationale,
        primary_reason=primary_reason,
    )


def evaluate_row(
    row: pd.Series,
    *,
    config: BaselineStrategyConfig | None = None,
) -> StrategyDecision:
    """
    Evaluate one feature/regime row.

    No future information is accessed.

    Parameters
    ----------
    row:
        One decision-time feature row joined with its Phase 6 regime.

    config:
        Explicit baseline strategy configuration.
    """

    if config is None:
        config = BaselineStrategyConfig()

    _validate_row(row)

    regime = str(row["regime"])
    probability = float(row["regime_probability"])
    vwap_distance = float(row["vwap_distance_pct"])
    rvol = float(row["rvol_20"])

    higher_high = bool(row["higher_high"])
    higher_low = bool(row["higher_low"])
    lower_low = bool(row["lower_low"])
    lower_high = bool(row["lower_high"])

    # Reject weak/uncertain regime classifications.
    if probability < config.minimum_regime_probability:
        return _decision(
            row,
            StrategyDirection.NO_TRADE,
            "Regime probability below baseline threshold.",
            config,
            NoTradeReason.REGIME_CONFIDENCE_TOO_LOW,
        )

    # ---------------------------------------------------------------
    # LONG setup
    # ---------------------------------------------------------------
    if (
        regime == MarketRegime.TREND_UP.value
        and vwap_distance > 0.0
        and rvol >= config.minimum_rvol
        and higher_high
        and higher_low
    ):
        return _decision(
            row,
            StrategyDirection.LONG,
            (
                "TREND_UP + above VWAP + sufficient RVOL "
                "+ higher-high + higher-low."
            ),
            config,
        )

    # ---------------------------------------------------------------
    # SHORT setup
    # ---------------------------------------------------------------
    if (
        regime == MarketRegime.TREND_DOWN.value
        and vwap_distance < 0.0
        and rvol >= config.minimum_rvol
        and lower_low
        and lower_high
    ):
        return _decision(
            row,
            StrategyDirection.SHORT,
            (
                "TREND_DOWN + below VWAP + sufficient RVOL "
                "+ lower-low + lower-high."
            ),
            config,
        )

    # ---------------------------------------------------------------
    # No qualifying setup.
    # ---------------------------------------------------------------
    return _decision(
        row,
        StrategyDirection.NO_TRADE,
        "Baseline conditions are not simultaneously satisfied.",
        config,
    )


def evaluate(
    features: pd.DataFrame,
    *,
    config: BaselineStrategyConfig | None = None,
) -> pd.DataFrame:
    """
    Evaluate a complete feature/regime dataset.

    The output contains one decision for each input row.
    """

    if config is None:
        config = BaselineStrategyConfig()

    if not isinstance(features, pd.DataFrame):
        raise TypeError("features must be a pandas DataFrame")

    if features.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "symbol",
                "direction",
                "strategy_version",
                "rationale",
            ]
        )

    decisions = [
        evaluate_row(row, config=config)
        for _, row in features.iterrows()
    ]

    return pd.DataFrame(
        [
            {
                "timestamp": decision.timestamp,
                "symbol": decision.symbol,
                "direction": decision.direction.value,
                "strategy_version": decision.strategy_version,
                "rationale": decision.rationale,
            }
            for decision in decisions
        ]
    )