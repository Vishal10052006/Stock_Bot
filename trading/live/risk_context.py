"""Explicit live account/portfolio state contract for V1 manual Risk.

No account value is synthesized here. Every decision-time field required by
Risk must be supplied by an external observation source.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from trading.risk.contracts import RiskPositionContext
from trading.risk.kill_switch import KillSwitchState


@dataclass(frozen=True, slots=True)
class LiveManualRiskContext:
    """Observed account, portfolio and system state for one decision."""

    as_of: pd.Timestamp
    source: str
    available_equity: float
    day_start_equity: float
    available_cash: float
    peak_equity: float
    realized_pnl: float
    unrealized_pnl: float
    open_positions: int
    trades_today: int
    gross_exposure: float
    symbol_already_open: bool
    position_context: RiskPositionContext | None
    liquidity_available: bool
    kill_switch_active: bool

    sector: str | None
    symbol_exposure: Mapping[str, float]
    sector_exposure: Mapping[str, float]
    pairwise_correlation: Mapping[str, float]

    atr: float | None
    high_volatility: bool

    market_data_valid: bool
    system_ready: bool
    kill_switch_state: KillSwitchState | None
    max_age_seconds: float

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.as_of)
        if timestamp.tzinfo is None:
            raise ValueError("risk context as_of must be timezone-aware")
        if not self.source.strip():
            raise ValueError("risk context source must not be empty")
        if not math.isfinite(float(self.max_age_seconds)) or self.max_age_seconds <= 0:
            raise ValueError("risk context max_age_seconds must be positive and finite")

        for name, value in (
            ("available_equity", self.available_equity),
            ("day_start_equity", self.day_start_equity),
            ("available_cash", self.available_cash),
            ("peak_equity", self.peak_equity),
            ("realized_pnl", self.realized_pnl),
            ("unrealized_pnl", self.unrealized_pnl),
            ("gross_exposure", self.gross_exposure),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"risk context {name} must be finite")

        if self.available_equity <= 0:
            raise ValueError("risk context available_equity must be positive")
        if self.day_start_equity <= 0:
            raise ValueError("risk context day_start_equity must be positive")
        if self.available_cash < 0:
            raise ValueError("risk context available_cash must be non-negative")
        if self.peak_equity <= 0:
            raise ValueError("risk context peak_equity must be positive")
        if self.gross_exposure < 0:
            raise ValueError("risk context gross_exposure must be non-negative")
        if self.open_positions < 0:
            raise ValueError("risk context open_positions must be non-negative")
        if self.trades_today < 0:
            raise ValueError("risk context trades_today must be non-negative")
        if self.position_context is not None and not isinstance(
            self.position_context,
            RiskPositionContext,
        ):
            raise TypeError("risk context position_context must be RiskPositionContext")

        if self.atr is not None and (
            not math.isfinite(float(self.atr)) or self.atr < 0
        ):
            raise ValueError("risk context atr must be finite and non-negative")

        symbol_exposure = {
            str(key).strip().upper(): float(value)
            for key, value in self.symbol_exposure.items()
        }
        sector_exposure = {
            str(key).strip(): float(value)
            for key, value in self.sector_exposure.items()
        }
        pairwise_correlation = {
            str(key).strip().upper(): float(value)
            for key, value in self.pairwise_correlation.items()
        }

        if any(
            not math.isfinite(value) or value < 0
            for value in symbol_exposure.values()
        ):
            raise ValueError(
                "risk context symbol_exposure values must be finite and non-negative"
            )
        if any(
            not math.isfinite(value) or value < 0
            for value in sector_exposure.values()
        ):
            raise ValueError(
                "risk context sector_exposure values must be finite and non-negative"
            )
        if any(
            not math.isfinite(value) or not -1.0 <= value <= 1.0
            for value in pairwise_correlation.values()
        ):
            raise ValueError(
                "risk context pairwise_correlation values must be finite and in [-1, 1]"
            )

        object.__setattr__(self, "as_of", timestamp)
        object.__setattr__(self, "source", self.source.strip())
        object.__setattr__(self, "symbol_exposure", symbol_exposure)
        object.__setattr__(self, "sector_exposure", sector_exposure)
        object.__setattr__(self, "pairwise_correlation", pairwise_correlation)

    def validation_error(
        self,
        *,
        observed_at: pd.Timestamp,
        decision_timestamp: pd.Timestamp,
    ) -> str | None:
        """Return a safety-block reason for stale or causally invalid state."""
        observed = pd.Timestamp(observed_at)
        decision = pd.Timestamp(decision_timestamp)
        if observed.tzinfo is None or decision.tzinfo is None:
            return "risk context and decision timestamps must be timezone-aware"

        if decision > observed:
            return "decision timestamp is in the future relative to risk observation"

        if observed < self.as_of:
            return "risk context observation timestamp precedes its state timestamp"

        age = (observed - self.as_of).total_seconds()
        if age > self.max_age_seconds:
            return (
                f"risk context is stale by {age:.1f}s; "
                f"maximum age is {self.max_age_seconds:.1f}s"
            )

        # Account state is observed after the candle closes in a real runtime.
        # Causality therefore uses the supplied observation boundary rather than
        # falsely rewriting the broker snapshot timestamp to the candle time.
        if self.as_of > observed:
            return "risk context state timestamp is newer than observation time"

        return None


__all__ = ["LiveManualRiskContext"]
