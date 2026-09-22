"""Deterministic pre-trade Risk Engine for STOCK_BOT.

The Risk Engine sits downstream of Strategy and has veto authority over a
candidate. It owns risk-budgeting, position sizing, target construction and
hard portfolio/session limits. It never places an order or contacts a broker.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from trading.signals.models import TradeCandidate
from trading.strategy.models import StrategyDirection

from .gate import RiskDecision, RiskDecisionStatus


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Frozen research/paper risk limits from TRADING_SPECIFICATION.md."""

    risk_per_trade: float = 0.005
    max_daily_loss: float = 0.015
    max_trades_per_day: int = 5
    max_open_positions: int = 3
    max_gross_exposure: float = 0.75
    target_multiple_r: float = 1.5
    quantity_step: float = 1.0
    risk_version: str = "RISK-v1.0"

    def __post_init__(self) -> None:
        if not 0.0 < self.risk_per_trade <= 1.0:
            raise ValueError("risk_per_trade must be in (0, 1]")
        if not 0.0 < self.max_daily_loss <= 1.0:
            raise ValueError("max_daily_loss must be in (0, 1]")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be positive")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be positive")
        if not 0.0 < self.max_gross_exposure <= 1.0:
            raise ValueError("max_gross_exposure must be in (0, 1]")
        if self.target_multiple_r <= 0:
            raise ValueError("target_multiple_r must be positive")
        if self.quantity_step <= 0:
            raise ValueError("quantity_step must be positive")
        if not self.risk_version.strip():
            raise ValueError("risk_version must not be empty")


@dataclass(frozen=True, slots=True)
class RiskInput:
    """Decision-time portfolio/account state supplied to the Risk Engine."""

    timestamp: pd.Timestamp
    symbol: str
    candidate: TradeCandidate
    available_equity: float
    day_start_equity: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    open_positions: int = 0
    trades_today: int = 0
    gross_exposure: float = 0.0
    symbol_already_open: bool = False
    liquidity_available: bool = True
    kill_switch_active: bool = False

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)

        if timestamp.tzinfo is None:
            raise ValueError(
                "risk input timestamp must be timezone-aware"
            )

        if not self.symbol.strip():
            raise ValueError(
                "risk input symbol must not be empty"
            )

        if not isinstance(self.candidate, TradeCandidate):
            raise TypeError(
                "candidate must be a TradeCandidate"
            )

        if timestamp != self.candidate.timestamp:
            raise ValueError(
                "risk timestamp must match candidate timestamp"
            )

        if self.symbol.strip().upper() != self.candidate.symbol.upper():
            raise ValueError(
                "risk symbol must match candidate symbol"
            )

        for name, value in (
            ("available_equity", self.available_equity),
            ("day_start_equity", self.day_start_equity),
            ("realized_pnl", self.realized_pnl),
            ("unrealized_pnl", self.unrealized_pnl),
            ("gross_exposure", self.gross_exposure),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(
                    f"{name} must be finite"
                )

        if self.available_equity <= 0:
            raise ValueError(
                "available_equity must be positive"
            )

        if self.day_start_equity <= 0:
            raise ValueError(
                "day_start_equity must be positive"
            )

        if self.gross_exposure < 0:
            raise ValueError(
                "gross_exposure must be non-negative"
            )

        if self.open_positions < 0:
            raise ValueError(
                "open_positions must be non-negative"
            )

        if self.trades_today < 0:
            raise ValueError(
                "trades_today must be non-negative"
            )


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Auditable risk result including proposed position economics."""

    decision: RiskDecision
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    risk_budget: float | None = None
    stop_distance: float | None = None
    position_size: float | None = None
    gross_exposure_after: float | None = None
    daily_pnl: float | None = None


def _strategy_direction(
    candidate: TradeCandidate,
) -> StrategyDirection:
    """Map the research candidate direction into the Risk contract."""

    if candidate.direction.value == "LONG":
        return StrategyDirection.LONG

    if candidate.direction.value == "SHORT":
        return StrategyDirection.SHORT

    raise ValueError(
        "candidate direction must be LONG or SHORT"
    )


class RiskEngine:
    """Apply deterministic risk limits to one Strategy-produced candidate."""

    def __init__(
        self,
        config: RiskConfig | None = None,
    ) -> None:
        self.config = config or RiskConfig()

    def evaluate(
        self,
        value: RiskInput,
    ) -> RiskAssessment:
        """Return an APPROVED/REJECTED assessment without execution."""

        if not isinstance(value, RiskInput):
            raise TypeError(
                "value must be a RiskInput"
            )

        candidate = value.candidate
        daily_pnl = value.realized_pnl + value.unrealized_pnl
        daily_loss_limit = (
            value.day_start_equity * self.config.max_daily_loss
        )

        if value.kill_switch_active:
            return self._reject(
                value,
                "Kill switch is active.",
                daily_pnl,
            )

        if not value.liquidity_available:
            return self._reject(
                value,
                "Liquidity is insufficient.",
                daily_pnl,
            )

        if value.trades_today >= self.config.max_trades_per_day:
            return self._reject(
                value,
                "Maximum daily trade entries reached.",
                daily_pnl,
            )

        if daily_pnl <= -daily_loss_limit:
            return self._reject(
                value,
                "Daily loss limit reached.",
                daily_pnl,
            )

        if value.open_positions >= self.config.max_open_positions:
            return self._reject(
                value,
                "Maximum open positions reached.",
                daily_pnl,
            )

        if value.symbol_already_open:
            return self._reject(
                value,
                "Symbol already has an open position.",
                daily_pnl,
            )

        entry = candidate.entry_price
        stop = candidate.stop_price
        stop_distance = candidate.stop_distance

        if not math.isfinite(stop_distance) or stop_distance <= 0:
            return self._reject(
                value,
                "Invalid stop distance.",
                daily_pnl,
            )

        risk_budget = (
            value.available_equity
            * self.config.risk_per_trade
        )

        raw_quantity = risk_budget / stop_distance

        quantity = (
            math.floor(
                raw_quantity / self.config.quantity_step
            )
            * self.config.quantity_step
        )

        if quantity <= 0:
            return self._reject(
                value,
                "Risk budget cannot produce a valid quantity.",
                daily_pnl,
            )

        target_distance = (
            stop_distance
            * self.config.target_multiple_r
        )

        if candidate.direction.value == "LONG":
            target = entry + target_distance
        else:
            target = entry - target_distance

        if target <= 0 or not math.isfinite(target):
            return self._reject(
                value,
                "Target construction is invalid.",
                daily_pnl,
            )

        gross_after = (
            value.gross_exposure
            + entry * quantity
        )

        exposure_limit = (
            value.available_equity
            * self.config.max_gross_exposure
        )

        if gross_after > exposure_limit + 1e-12:
            return self._reject(
                value,
                "Maximum gross exposure would be exceeded.",
                daily_pnl,
            )

        decision = RiskDecision(
            timestamp=value.timestamp,
            symbol=value.symbol,
            status=RiskDecisionStatus.APPROVED,
            strategy_direction=_strategy_direction(candidate),
            reason="Candidate passed deterministic risk controls.",
            risk_version=self.config.risk_version,
        )

        return RiskAssessment(
            decision=decision,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            risk_budget=risk_budget,
            stop_distance=stop_distance,
            position_size=quantity,
            gross_exposure_after=gross_after,
            daily_pnl=daily_pnl,
        )

    def _reject(
        self,
        value: RiskInput,
        reason: str,
        daily_pnl: float,
    ) -> RiskAssessment:
        """Create a rejection with no sizing side effects."""

        return RiskAssessment(
            decision=RiskDecision(
                timestamp=value.timestamp,
                symbol=value.symbol,
                status=RiskDecisionStatus.REJECTED,
                strategy_direction=_strategy_direction(
                    value.candidate
                ),
                reason=reason,
                risk_version=self.config.risk_version,
            ),
            daily_pnl=daily_pnl,
        )
