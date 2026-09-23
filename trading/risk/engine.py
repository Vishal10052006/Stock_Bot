"""Deterministic pre-trade Risk Engine for STOCK_BOT.

The Risk Engine is downstream of Strategy and upstream of Execution. It has
veto authority, owns risk-first sizing and hard portfolio/session limits, and
never places broker orders.

References:
- TRADING_SPECIFICATION.md
- docs/RISK_ENGINE.md
- docs/PHASE_11_DIRECT_BUILD.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

import pandas as pd

from trading.signals.models import TradeCandidate
from trading.strategy.models import StrategyDirection

from .concentration import check_sector_exposure, check_symbol_exposure
from .contracts import RiskReasonCode
from .correlation import correlation_exposure_allowed
from .daily_limits import DailyRiskState, daily_loss_limit_reached
from .exposure import gross_exposure_after
from .kill_switch import KillSwitchState
from .position_sizing import calculate_position_size, floor_to_step
from .stop_loss import validate_stop
from .target import build_target
from .volatility import volatility_size_factor
from .gate import RiskDecision, RiskDecisionStatus


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Frozen research/paper risk limits plus opt-in advanced controls."""

    risk_per_trade: float = 0.005
    max_daily_loss: float = 0.015
    max_trades_per_day: int = 5
    max_open_positions: int = 3
    max_gross_exposure: float = 0.75
    target_multiple_r: float = 1.5
    quantity_step: float = 1.0
    risk_version: str = "RISK-v1.0"

    # Advanced controls are intentionally disabled until their numeric policy
    # is explicitly frozen and validated by later research phases.
    max_symbol_exposure_fraction: float | None = None
    max_sector_exposure_fraction: float | None = None
    minimum_abs_correlation: float | None = None
    max_correlated_exposure_fraction: float | None = None
    high_volatility_factor: float = 1.0
    max_atr_fraction: float | None = None
    max_drawdown_fraction: float | None = None

    # The frozen v1 paper policy treats exposure violations as NO_TRADE.
    # Volatility/concentration policies can use RESIZE once explicitly enabled.
    allow_resize: bool = False

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
        if not 0.0 < self.high_volatility_factor <= 1.0:
            raise ValueError("high_volatility_factor must be in (0, 1]")
        for name, value in (
            ("max_symbol_exposure_fraction", self.max_symbol_exposure_fraction),
            ("max_sector_exposure_fraction", self.max_sector_exposure_fraction),
            ("max_correlated_exposure_fraction", self.max_correlated_exposure_fraction),
            ("max_atr_fraction", self.max_atr_fraction),
            ("max_drawdown_fraction", self.max_drawdown_fraction),
        ):
            if value is not None and not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must be in (0, 1] when configured")
        if (
            self.minimum_abs_correlation is not None
            and not 0.0 <= self.minimum_abs_correlation <= 1.0
        ):
            raise ValueError("minimum_abs_correlation must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class RiskInput:
    """Decision-time account, portfolio and market state supplied to Risk."""

    timestamp: pd.Timestamp
    symbol: str
    candidate: TradeCandidate
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
    liquidity_available: bool = True
    kill_switch_active: bool = False

    # Optional advanced portfolio context.
    sector: str | None = None
    symbol_exposure: Mapping[str, float] = field(default_factory=dict)
    sector_exposure: Mapping[str, float] = field(default_factory=dict)
    pairwise_correlation: Mapping[str, float] = field(default_factory=dict)

    # Optional volatility context.
    atr: float | None = None
    high_volatility: bool = False

    # Independent system-health boundaries.
    market_data_valid: bool = True
    system_ready: bool = True
    kill_switch_state: KillSwitchState | None = None

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)

        if timestamp.tzinfo is None:
            raise ValueError("risk input timestamp must be timezone-aware")

        if not self.symbol.strip():
            raise ValueError("risk input symbol must not be empty")

        if not isinstance(self.candidate, TradeCandidate):
            raise TypeError("candidate must be a TradeCandidate")

        if timestamp != self.candidate.timestamp:
            raise ValueError("risk timestamp must match candidate timestamp")

        if self.symbol.strip().upper() != self.candidate.symbol.upper():
            raise ValueError("risk symbol must match candidate symbol")

        for name, value in (
            ("available_equity", self.available_equity),
            ("day_start_equity", self.day_start_equity),
            ("realized_pnl", self.realized_pnl),
            ("unrealized_pnl", self.unrealized_pnl),
            ("gross_exposure", self.gross_exposure),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

        if self.available_equity <= 0:
            raise ValueError("available_equity must be positive")

        if self.day_start_equity <= 0:
            raise ValueError("day_start_equity must be positive")

        if self.available_cash is not None and (
            not math.isfinite(float(self.available_cash))
            or self.available_cash < 0
        ):
            raise ValueError("available_cash must be finite and non-negative")

        if self.peak_equity is not None and (
            not math.isfinite(float(self.peak_equity))
            or self.peak_equity <= 0
        ):
            raise ValueError("peak_equity must be positive and finite")

        if self.gross_exposure < 0:
            raise ValueError("gross_exposure must be non-negative")

        if self.open_positions < 0:
            raise ValueError("open_positions must be non-negative")

        if self.trades_today < 0:
            raise ValueError("trades_today must be non-negative")

        if self.atr is not None and (
            not math.isfinite(float(self.atr)) or self.atr < 0
        ):
            raise ValueError("atr must be finite and non-negative")

        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(
            self,
            "symbol_exposure",
            {str(k).strip().upper(): float(v) for k, v in self.symbol_exposure.items()},
        )
        object.__setattr__(
            self,
            "sector_exposure",
            {str(k).strip(): float(v) for k, v in self.sector_exposure.items()},
        )
        object.__setattr__(
            self,
            "pairwise_correlation",
            {str(k).strip().upper(): float(v) for k, v in self.pairwise_correlation.items()},
        )


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Immutable, auditable risk result including position economics."""

    decision: RiskDecision
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    risk_budget: float | None = None
    stop_distance: float | None = None
    position_size: float | None = None
    requested_position_size: float | None = None
    gross_exposure_after: float | None = None
    daily_pnl: float | None = None
    volatility_factor: float | None = None


def _strategy_direction(candidate: TradeCandidate) -> StrategyDirection:
    """Map the research candidate direction into the Risk contract."""
    if candidate.direction.value == "LONG":
        return StrategyDirection.LONG
    if candidate.direction.value == "SHORT":
        return StrategyDirection.SHORT
    raise ValueError("candidate direction must be LONG or SHORT")


class RiskEngine:
    """Apply deterministic hard risk controls to one trade candidate."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def evaluate(self, value: RiskInput) -> RiskAssessment:
        """Evaluate one candidate without placing or authorizing an order."""
        if not isinstance(value, RiskInput):
            raise TypeError("value must be a RiskInput")

        candidate = value.candidate
        direction = _strategy_direction(candidate)
        daily_pnl = value.realized_pnl + value.unrealized_pnl

        # 1. Independent safety and data-health gates.
        if not value.system_ready:
            return self._reject(
                value,
                "Risk system is not ready.",
                daily_pnl,
                RiskReasonCode.SYSTEM_NOT_READY,
            )

        kill_active = value.kill_switch_active or (
            value.kill_switch_state.active
            if value.kill_switch_state is not None
            else False
        )
        if kill_active:
            return self._reject(
                value,
                "Kill switch is active.",
                daily_pnl,
                RiskReasonCode.KILL_SWITCH_ACTIVE,
            )

        if not value.market_data_valid:
            return self._reject(
                value,
                "Market data is invalid or unavailable.",
                daily_pnl,
                RiskReasonCode.STALE_MARKET_DATA,
            )

        if not value.liquidity_available:
            return self._reject(
                value,
                "Liquidity is insufficient.",
                daily_pnl,
                RiskReasonCode.LIQUIDITY_INSUFFICIENT,
            )

        # 2. Hard session/account limits.
        daily_state = DailyRiskState(
            day_start_equity=value.day_start_equity,
            realized_pnl=value.realized_pnl,
            unrealized_pnl=value.unrealized_pnl,
            trades_today=value.trades_today,
            open_positions=value.open_positions,
        )
        if daily_loss_limit_reached(
            state=daily_state,
            max_daily_loss=self.config.max_daily_loss,
        ):
            return self._reject(
                value,
                "Daily loss limit reached.",
                daily_pnl,
                RiskReasonCode.DAILY_LOSS_LIMIT,
            )

        if value.trades_today >= self.config.max_trades_per_day:
            return self._reject(
                value,
                "Maximum daily trade entries reached.",
                daily_pnl,
                RiskReasonCode.MAX_TRADES_REACHED,
            )

        if value.open_positions >= self.config.max_open_positions:
            return self._reject(
                value,
                "Maximum open positions reached.",
                daily_pnl,
                RiskReasonCode.MAX_OPEN_POSITIONS,
            )

        if value.symbol_already_open:
            return self._reject(
                value,
                "Symbol already has an open position.",
                daily_pnl,
                RiskReasonCode.DUPLICATE_SYMBOL,
            )

        # Drawdown is optional because the frozen specification defines daily
        # loss but does not freeze a numeric total-drawdown cap.
        if (
            self.config.max_drawdown_fraction is not None
            and value.peak_equity is not None
            and value.available_equity
            <= value.peak_equity * (1.0 - self.config.max_drawdown_fraction)
        ):
            return self._reject(
                value,
                "Maximum drawdown limit reached.",
                daily_pnl,
                RiskReasonCode.DAILY_LOSS_LIMIT,
            )

        # 3. Candidate price/stop validation. Stop construction itself stays
        # in trading.signals.candidate and is never duplicated here.
        entry = float(candidate.entry_price)
        stop = float(candidate.stop_price)

        try:
            stop_distance = validate_stop(
                direction=direction,
                entry_price=entry,
                stop_price=stop,
            )
        except ValueError as exc:
            code = (
                RiskReasonCode.INVALID_PRICE
                if "price" in str(exc).lower()
                else RiskReasonCode.INVALID_STOP
            )
            return self._reject(
                value,
                str(exc),
                daily_pnl,
                code,
            )

        # 4. Risk-first sizing.
        sizing = calculate_position_size(
            available_equity=value.available_equity,
            risk_per_trade=self.config.risk_per_trade,
            stop_distance=stop_distance,
            quantity_step=self.config.quantity_step,
        )

        requested_quantity = sizing.quantity

        # Available cash is an optional account-level constraint. It can only
        # reduce risk-first size; it never increases it.
        if value.available_cash is not None:
            cash_quantity = floor_to_step(
                value.available_cash / entry,
                self.config.quantity_step,
            )
            if cash_quantity < requested_quantity:
                if not self.config.allow_resize:
                    return self._reject(
                        value,
                        "Available cash cannot support the risk-first quantity.",
                        daily_pnl,
                        RiskReasonCode.INVALID_RISK_STATE,
                    )
                requested_quantity = cash_quantity

        if requested_quantity <= 0:
            return self._reject(
                value,
                "Risk budget cannot produce a valid quantity.",
                daily_pnl,
                RiskReasonCode.ZERO_POSITION_SIZE,
            )

        # 5. Deterministic target construction.
        try:
            target = build_target(
                direction=direction,
                entry_price=entry,
                stop_distance=stop_distance,
                target_multiple_r=self.config.target_multiple_r,
            )
        except ValueError as exc:
            return self._reject(
                value,
                str(exc),
                daily_pnl,
                RiskReasonCode.INVALID_TARGET,
            )

        # 6. Optional volatility policy. Default factor is 1.0, matching the
        # current frozen specification while keeping the extension point ready.
        try:
            vol_factor = volatility_size_factor(
                entry_price=entry,
                atr=value.atr,
                high_volatility=value.high_volatility,
                high_volatility_factor=self.config.high_volatility_factor,
                max_atr_fraction=self.config.max_atr_fraction,
            )
        except ValueError as exc:
            return self._reject(
                value,
                str(exc),
                daily_pnl,
                RiskReasonCode.VOLATILITY_LIMIT,
            )

        if vol_factor <= 0:
            return self._reject(
                value,
                "Volatility policy blocks the proposed trade.",
                daily_pnl,
                RiskReasonCode.VOLATILITY_LIMIT,
            )

        quantity = floor_to_step(
            requested_quantity * vol_factor,
            self.config.quantity_step,
        )

        resized = quantity < requested_quantity
        if quantity <= 0:
            return self._reject(
                value,
                "Volatility adjustment leaves no valid quantity.",
                daily_pnl,
                RiskReasonCode.ZERO_POSITION_SIZE,
            )

        if resized and not self.config.allow_resize:
            return self._reject(
                value,
                "Volatility policy requires resizing, but resizing is disabled.",
                daily_pnl,
                RiskReasonCode.VOLATILITY_LIMIT,
            )

        proposed_value = entry * quantity

        # 7. Gross exposure is a frozen hard v1 control. A violation remains
        # NO_TRADE unless an explicitly validated resize policy is enabled.
        exposure_limit = (
            value.available_equity * self.config.max_gross_exposure
        )
        gross_after = gross_exposure_after(
            current_gross_exposure=value.gross_exposure,
            entry_price=entry,
            quantity=quantity,
        )

        if gross_after > exposure_limit + 1e-12:
            if self.config.allow_resize:
                remaining_exposure = max(
                    0.0,
                    exposure_limit - value.gross_exposure,
                )
                exposure_quantity = floor_to_step(
                    remaining_exposure / entry,
                    self.config.quantity_step,
                )
                if exposure_quantity <= 0:
                    return self._reject(
                        value,
                        "Maximum gross exposure would be exceeded.",
                        daily_pnl,
                        RiskReasonCode.MAX_GROSS_EXPOSURE,
                    )
                quantity = min(quantity, exposure_quantity)
                resized = quantity < requested_quantity
                proposed_value = entry * quantity
                gross_after = gross_exposure_after(
                    current_gross_exposure=value.gross_exposure,
                    entry_price=entry,
                    quantity=quantity,
                )
            else:
                return self._reject(
                    value,
                    "Maximum gross exposure would be exceeded.",
                    daily_pnl,
                    RiskReasonCode.MAX_GROSS_EXPOSURE,
                )

        # 8. Optional concentration/correlation controls.
        if not check_symbol_exposure(
            symbol=value.symbol,
            proposed_value=proposed_value,
            existing_by_symbol=value.symbol_exposure,
            max_symbol_exposure_fraction=self.config.max_symbol_exposure_fraction,
            equity=value.available_equity,
        ):
            return self._reject(
                value,
                "Maximum symbol exposure would be exceeded.",
                daily_pnl,
                RiskReasonCode.SYMBOL_EXPOSURE_LIMIT,
            )

        if not check_sector_exposure(
            sector=value.sector,
            proposed_value=proposed_value,
            existing_by_sector=value.sector_exposure,
            max_sector_exposure_fraction=self.config.max_sector_exposure_fraction,
            equity=value.available_equity,
        ):
            return self._reject(
                value,
                "Maximum sector exposure would be exceeded.",
                daily_pnl,
                RiskReasonCode.SECTOR_EXPOSURE_LIMIT,
            )

        if not correlation_exposure_allowed(
            symbol=value.symbol,
            proposed_value=proposed_value,
            existing_by_symbol=value.symbol_exposure,
            pairwise_correlation=value.pairwise_correlation,
            equity=value.available_equity,
            minimum_abs_correlation=self.config.minimum_abs_correlation,
            max_correlated_exposure_fraction=self.config.max_correlated_exposure_fraction,
        ):
            return self._reject(
                value,
                "Maximum correlated exposure would be exceeded.",
                daily_pnl,
                RiskReasonCode.CORRELATION_LIMIT,
            )

        decision = RiskDecision(
            timestamp=value.timestamp,
            symbol=value.symbol,
            status=RiskDecisionStatus.APPROVED,
            strategy_direction=direction,
            reason=(
                "Candidate passed deterministic risk controls."
                if not resized
                else "Candidate passed risk controls after deterministic resizing."
            ),
            risk_version=self.config.risk_version,
            reason_code=(
                RiskReasonCode.RESIZED
                if resized
                else RiskReasonCode.APPROVED
            ),
            resized=resized,
        )

        return RiskAssessment(
            decision=decision,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            risk_budget=sizing.risk_budget,
            stop_distance=stop_distance,
            position_size=quantity,
            requested_position_size=requested_quantity,
            gross_exposure_after=gross_after,
            daily_pnl=daily_pnl,
            volatility_factor=vol_factor,
        )

    def _reject(
        self,
        value: RiskInput,
        reason: str,
        daily_pnl: float,
        reason_code: RiskReasonCode,
    ) -> RiskAssessment:
        """Create an auditable rejection with no execution side effects."""
        return RiskAssessment(
            decision=RiskDecision(
                timestamp=value.timestamp,
                symbol=value.symbol,
                status=RiskDecisionStatus.REJECTED,
                strategy_direction=_strategy_direction(value.candidate),
                reason=reason,
                risk_version=self.config.risk_version,
                reason_code=reason_code,
            ),
            daily_pnl=daily_pnl,
        )


__all__ = [
    "RiskAssessment",
    "RiskConfig",
    "RiskEngine",
    "RiskInput",
]
