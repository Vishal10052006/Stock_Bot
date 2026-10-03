"""Live-market account and portfolio state required by manual V1 Risk evaluation.

This contract is deliberately separate from the paper/virtual account runtime.
It carries observed decision-time state into the existing deterministic Risk
Engine; it never places or authorizes broker orders.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

import pandas as pd

from trading.risk.contracts import RiskPositionContext
from trading.risk.kill_switch import KillSwitchState


@dataclass(frozen=True, slots=True)
class LiveManualRiskContext:
    """Auditable account/portfolio/system snapshot for one manual decision."""

    as_of: pd.Timestamp
    source: str

    available_equity: float
    day_start_equity: float
    available_cash: float | None = None
    peak_equity: float | None = None

    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    open_positions: int = 0
    trades_today: int = 0
    gross_exposure: float = 0.0
    symbol_already_open: bool = False
    position_context: RiskPositionContext | None = None
    liquidity_available: bool = True
    kill_switch_active: bool = False

    sector: str | None = None
    symbol_exposure: Mapping[str, float] = field(default_factory=dict)
    sector_exposure: Mapping[str, float] = field(default_factory=dict)
    pairwise_correlation: Mapping[str, float] = field(default_factory=dict)

    atr: float | None = None
    high_volatility: bool = False

    market_data_valid: bool = True
    system_ready: bool = True
    kill_switch_state: KillSwitchState | None = None

    max_age_seconds: float = 30.0

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
        if self.available_cash is not None and (
            not math.isfinite(float(self.available_cash))
            or self.available_cash < 0
        ):
            raise ValueError(
                "risk context available_cash must be finite and non-negative"
            )
        if self.peak_equity is not None and (
            not math.isfinite(float(self.peak_equity))
            or self.peak_equity <= 0
        ):
            raise ValueError("risk context peak_equity must be positive and finite")
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

    def validation_error(self, decision_timestamp: pd.Timestamp) -> str | None:
        """Return a safety-block reason when the snapshot is missing/stale."""
        decision = pd.Timestamp(decision_timestamp)
        if decision.tzinfo is None:
            return "decision timestamp must be timezone-aware"

        age = (decision - self.as_of).total_seconds()
        if age < 0:
            return "risk context is newer than the decision timestamp"
        if age > self.max_age_seconds:
            return (
                f"risk context is stale by {age:.1f}s; "
                f"maximum age is {self.max_age_seconds:.1f}s"
            )
        return None


__all__ = ["LiveManualRiskContext"]
