"""
Models for the deterministic Phase 8 baseline strategy.

The baseline strategy deliberately produces only a trading direction
decision. Position sizing, stop-loss enforcement, exposure limits,
and execution belong to later trading layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class StrategyDirection(str, Enum):
    """Allowed Phase 8 strategy decisions."""

    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class BaselineStrategyConfig:
    """
    Configuration for BaselineStrategy v1.0.

    These values are explicit configuration rather than values learned
    from the complete historical dataset.
    """

    minimum_rvol: float = 1.0
    minimum_regime_probability: float = 0.50
    strategy_version: str = "v1.0"

    def __post_init__(self) -> None:
        if self.minimum_rvol <= 0:
            raise ValueError("minimum_rvol must be positive")

        if not 0.0 <= self.minimum_regime_probability <= 1.0:
            raise ValueError(
                "minimum_regime_probability must be between 0 and 1"
            )

        if not self.strategy_version:
            raise ValueError("strategy_version must not be empty")


@dataclass(frozen=True)
class StrategyDecision:
    """Auditable result produced by BaselineStrategy."""

    timestamp: pd.Timestamp
    symbol: str
    direction: StrategyDirection
    strategy_version: str
    rationale: str