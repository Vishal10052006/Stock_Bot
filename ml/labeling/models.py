"""
Core data models for Phase 7 prediction-target labeling.

The labeling layer converts a future price path into an auditable
trading outcome without allowing future information to leak into
the decision-time feature set.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class TradeDirection(str, Enum):
    """Supported directional trade candidates."""

    LONG = "LONG"
    SHORT = "SHORT"


class PredictionLabel(str, Enum):
    """
    Three-class trading outcome.

    LONG_SUCCESS:
        The long candidate reached its target before its stop.

    SHORT_SUCCESS:
        The short candidate reached its target before its stop.

    NO_EDGE:
        Neither directional candidate produced a valid successful
        outcome within the evaluation horizon, or the outcome could
        not be determined reliably.
    """

    LONG_SUCCESS = "LONG_SUCCESS"
    SHORT_SUCCESS = "SHORT_SUCCESS"
    NO_EDGE = "NO_EDGE"


class AmbiguousOutcomePolicy(str, Enum):
    """
    Policy for candles where both relevant barriers are touched.

    OHLC data does not reveal the intrabar order of high/low events,
    so the conservative default is to reject the ambiguous outcome.
    """

    NO_EDGE = "NO_EDGE"


@dataclass(frozen=True)
class LabelingConfig:
    """
    Configuration for prediction-target construction.

    Defaults follow the frozen trading specification:
        - minimum target = 1.5R
        - maximum holding time = 60 minutes
        - primary timeframe = 5 minutes
        - therefore 12 bars maximum horizon
    """

    target_r_multiple: float = 1.5
    horizon_bars: int = 12
    ambiguous_policy: AmbiguousOutcomePolicy = (
        AmbiguousOutcomePolicy.NO_EDGE
    )

    def __post_init__(self) -> None:
        """Validate configuration invariants."""

        if self.target_r_multiple <= 0:
            raise ValueError("target_r_multiple must be greater than 0.")

        if self.horizon_bars <= 0:
            raise ValueError("horizon_bars must be greater than 0.")


@dataclass(frozen=True)
class TradeCandidate:
    """
    A candidate trade defined at a decision timestamp.

    The entry and stop are supplied by upstream logic. The labeling
    engine must never infer them from future candles.
    """

    timestamp: pd.Timestamp
    symbol: str
    direction: TradeDirection
    entry_price: float
    stop_price: float

    def __post_init__(self) -> None:
        """Validate the candidate trade."""

        if not isinstance(self.timestamp, pd.Timestamp):
            raise TypeError("timestamp must be a pandas Timestamp.")

        if not self.symbol:
            raise ValueError("symbol must not be empty.")

        if self.entry_price <= 0:
            raise ValueError("entry_price must be greater than 0.")

        if self.stop_price <= 0:
            raise ValueError("stop_price must be greater than 0.")

        if self.entry_price == self.stop_price:
            raise ValueError("entry_price and stop_price must differ.")

        if (
            self.direction == TradeDirection.LONG
            and self.stop_price >= self.entry_price
        ):
            raise ValueError(
                "A LONG stop_price must be below entry_price."
            )

        if (
            self.direction == TradeDirection.SHORT
            and self.stop_price <= self.entry_price
        ):
            raise ValueError(
                "A SHORT stop_price must be above entry_price."
            )


@dataclass(frozen=True)
class LabelingOutcome:
    """
    Auditable result produced by the labeling engine.

    `outcome_timestamp` identifies the future candle where the
    successful barrier or terminating condition was determined.
    """

    timestamp: pd.Timestamp
    symbol: str
    label: PredictionLabel

    entry_price: float
    stop_price: float
    target_price: float

    horizon_bars: int
    outcome_timestamp: Optional[pd.Timestamp]
    outcome_bars: Optional[int]
    outcome_reason: str

@dataclass(frozen=True)
class DecisionLabelingOutcome:
    """
    Decision-level prediction target.

    A single decision timestamp may have both a LONG and SHORT
    candidate evaluated independently. This model combines those
    directional outcomes into exactly one ML target.
    """

    timestamp: pd.Timestamp
    symbol: str
    label: PredictionLabel

    long_outcome: LabelingOutcome
    short_outcome: LabelingOutcome

    outcome_timestamp: Optional[pd.Timestamp]
    outcome_bars: Optional[int]
    outcome_reason: str