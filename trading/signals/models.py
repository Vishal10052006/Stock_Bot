"""
Models for research trade-candidate construction.

A TradeCandidate represents a fully specified directional research
candidate at a decision timestamp. It is produced after strategy
direction is known and before Phase 7 outcome labeling.

The candidate contains only decision-time information.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class CandidateDirection(str, Enum):
    """Allowed directional research candidates."""

    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class CandidateConfig:
    """
    Configuration for the structure + ATR candidate policy.

    These are explicit research parameters. They are not learned from
    the dataset and must remain fixed during an evaluation run.
    """

    atr_period: int = 14
    atr_multiplier: float = 1.5
    structural_lookback: int = 20
    policy_version: str = "structure_atr_v1.0"
    entry_method: str = "DECISION_CLOSE"

    def __post_init__(self) -> None:
        if self.atr_period <= 0:
            raise ValueError(
                "atr_period must be greater than zero"
            )

        if self.atr_multiplier <= 0:
            raise ValueError(
                "atr_multiplier must be positive"
            )

        if self.structural_lookback <= 0:
            raise ValueError(
                "structural_lookback must be greater than zero"
            )

        if not self.policy_version:
            raise ValueError(
                "policy_version must not be empty"
            )

        if self.entry_method != "DECISION_CLOSE":
            raise ValueError(
                "entry_method must be DECISION_CLOSE"
            )


@dataclass(frozen=True)
class TradeCandidate:
    """
    Fully specified directional research candidate.

    The stop is the initial planned stop used by Phase 7 labeling and
    later risk calculations. It must be constructed exclusively from
    information available at the decision timestamp.
    """

    timestamp: pd.Timestamp
    symbol: str
    direction: CandidateDirection
    entry_price: float
    stop_price: float
    policy_version: str

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)

        if timestamp.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware"
            )

        if not self.symbol or not self.symbol.strip():
            raise ValueError(
                "symbol must not be empty"
            )

        if self.entry_price <= 0:
            raise ValueError(
                "entry_price must be positive"
            )

        if self.stop_price <= 0:
            raise ValueError(
                "stop_price must be positive"
            )

        if not self.policy_version:
            raise ValueError(
                "policy_version must not be empty"
            )

        if self.direction == CandidateDirection.LONG:
            if self.stop_price >= self.entry_price:
                raise ValueError(
                    "LONG stop_price must be below entry_price"
                )

        elif self.direction == CandidateDirection.SHORT:
            if self.stop_price <= self.entry_price:
                raise ValueError(
                    "SHORT stop_price must be above entry_price"
                )

        else:
            raise ValueError(
                "direction must be LONG or SHORT"
            )

    @property
    def stop_distance(self) -> float:
        """Return the absolute initial price risk per share."""

        return abs(
            self.entry_price - self.stop_price
        )
