"""Technical market-analysis worker.

This worker is deliberately deterministic.

It does not:
    - generate random BUY/SELL/HOLD signals
    - invent confidence values
    - execute trades
    - make final risk decisions

The production trading path will consume the causal Phase 4/5
indicator and feature pipeline before a strategy makes a signal.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from workers.base_worker import BaseWorker


class TechnicalWorker(BaseWorker):
    """Deterministic adapter for technical market context."""

    name = "technical_worker"
    capabilities = [
        "technical_analysis",
        "indicator_analysis",
        "feature_analysis",
    ]

    _REQUIRED_FEATURES = (
        "rsi_14",
        "macd_histogram",
        "roc_14",
        "vwap_distance_pct",
        "atr_normalized",
        "rvol_20",
        "price_ema_9_distance_pct",
        "price_ema_20_distance_pct",
        "price_ema_50_distance_pct",
        "ema_9_20_distance_pct",
        "ema_20_50_distance_pct",
    )

    def execute(self, task: Any) -> dict[str, Any]:
        """Analyze supplied technical features deterministically.

        A plain text command is not sufficient market context for
        technical analysis. In that case the worker returns a safe
        ``NO_SIGNAL`` result rather than inventing a trading signal.

        A DataFrame may be supplied directly, or through:
            {"features": dataframe}
        """

        features = self._extract_features(task)

        if features is None:
            return {
                "signal": "NO_SIGNAL",
                "confidence": None,
                "success": False,
                "reason": (
                    "Technical analysis requires a validated feature "
                    "dataset; no market feature data was supplied."
                ),
            }

        if features.empty:
            return {
                "signal": "NO_SIGNAL",
                "confidence": None,
                "success": False,
                "reason": "Technical feature dataset is empty.",
            }

        missing = [
            column
            for column in self._REQUIRED_FEATURES
            if column not in features.columns
        ]

        if missing:
            return {
                "signal": "NO_SIGNAL",
                "confidence": None,
                "success": False,
                "reason": (
                    "Technical feature dataset is missing required "
                    f"columns: {missing}"
                ),
            }

        row = features.iloc[-1]

        available = {
            column: self._safe_value(row[column])
            for column in self._REQUIRED_FEATURES
        }

        return {
            "signal": "NO_SIGNAL",
            "confidence": None,
            "success": True,
            "analysis": available,
            "reason": (
                "Technical market context calculated from supplied "
                "causal Phase 5 features. No trading decision was made."
            ),
        }

    @staticmethod
    def _extract_features(task: Any) -> pd.DataFrame | None:
        if isinstance(task, pd.DataFrame):
            return task

        if isinstance(task, Mapping):
            features = task.get("features")

            if isinstance(features, pd.DataFrame):
                return features

        return None

    @staticmethod
    def _safe_value(value: Any) -> Any:
        """Convert pandas missing values to None without changing data."""
        if pd.isna(value):
            return None

        if hasattr(value, "item"):
            try:
                return value.item()
            except (ValueError, TypeError):
                pass

        return value
