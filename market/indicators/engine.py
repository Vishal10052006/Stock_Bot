"""Unified indicator engine.

This module orchestrates the independently tested indicator families.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 4, Indicator Engine.
"""

from __future__ import annotations

import pandas as pd

from market.indicators.momentum import add_momentum_indicators
from market.indicators.structure import add_structure_indicators
from market.indicators.trend import add_trend_indicators
from market.indicators.volatility import add_volatility_indicators
from market.indicators.volume import add_volume_indicators


class IndicatorEngine:
    """Calculate the complete Phase 4 indicator set.

    The engine is intentionally limited to feature calculation.
    It does not generate trading signals or make execution decisions.
    """

    def __init__(
        self,
        *,
        trend_sma_period: int = 20,
        rsi_period: int = 14,
        roc_period: int = 14,
        atr_period: int = 14,
        bollinger_period: int = 20,
        bollinger_std: float = 2.0,
        realized_volatility_period: int = 20,
        rvol_period: int = 20,
        volume_change_period: int = 1,
        structure_period: int = 20,
        annualization_factor: float | None = None,
    ) -> None:
        """Configure indicator parameters."""
        self.trend_sma_period = trend_sma_period
        self.rsi_period = rsi_period
        self.roc_period = roc_period

        self.atr_period = atr_period
        self.bollinger_period = bollinger_period
        self.bollinger_std = bollinger_std
        self.realized_volatility_period = (
            realized_volatility_period
        )
        self.annualization_factor = annualization_factor

        self.rvol_period = rvol_period
        self.volume_change_period = volume_change_period

        self.structure_period = structure_period

    @staticmethod
    def _validate_input(data: pd.DataFrame) -> None:
        """Validate the minimum candle schema."""
        if not isinstance(data, pd.DataFrame):
            raise TypeError(
                "data must be a pandas DataFrame"
            )

        required = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing = required.difference(data.columns)

        if missing:
            raise ValueError(
                f"missing required OHLCV columns: "
                f"{sorted(missing)}"
            )

        if data.empty:
            raise ValueError(
                "data must not be empty"
            )

    def calculate(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Calculate all configured indicators.

        Returns:
            A new DataFrame containing the original OHLCV data
            plus all Phase 4 indicator columns.

        The input DataFrame is never mutated.
        """
        self._validate_input(data)

        result = data.copy()

        # ---------------------------------------------------------
        # Trend
        # ---------------------------------------------------------
        result = add_trend_indicators(
            result,
            sma_period=self.trend_sma_period,
        )

        # ---------------------------------------------------------
        # Momentum
        # ---------------------------------------------------------
        result = add_momentum_indicators(
            result,
            rsi_period=self.rsi_period,
            roc_period=self.roc_period,
        )

        # ---------------------------------------------------------
        # Volatility
        # ---------------------------------------------------------
        result = add_volatility_indicators(
            result,
            atr_period=self.atr_period,
            bollinger_period=self.bollinger_period,
            bollinger_std=self.bollinger_std,
            realized_volatility_period=(
                self.realized_volatility_period
            ),
            annualization_factor=self.annualization_factor,
        )

        # ---------------------------------------------------------
        # Volume
        # ---------------------------------------------------------
        result = add_volume_indicators(
            result,
            rvol_period=self.rvol_period,
            volume_change_period=(
                self.volume_change_period
            ),
        )

        # ---------------------------------------------------------
        # Price structure
        # ---------------------------------------------------------
        result = add_structure_indicators(
            result,
            period=self.structure_period,
        )

        return result


def calculate_indicators(
    data: pd.DataFrame,
    **kwargs: object,
) -> pd.DataFrame:
    """Convenience function for one-shot indicator calculation."""
    engine = IndicatorEngine(**kwargs)
    return engine.calculate(data)
