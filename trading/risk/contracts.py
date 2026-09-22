"""Risk Engine contracts.

Broker-neutral, immutable contracts for the deterministic Risk Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite

import pandas as pd

from trading.signals.models import CandidateDirection


class RiskDecisionStatus(str, Enum):
    """Final risk outcomes."""
    APPROVED = "APPROVED"
    APPROVED_WITH_RESTRICTIONS = "APPROVED_WITH_RESTRICTIONS"
    REDUCED = "REDUCED"
    REJECTED = "REJECTED"


class RiskReasonCode(str, Enum):
    """Controlled machine-readable risk decision reasons."""
    MAX_RISK_EXCEEDED = "MAX_RISK_EXCEEDED"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    SYMBOL_CONCENTRATION = "SYMBOL_CONCENTRATION"
    SECTOR_CONCENTRATION = "SECTOR_CONCENTRATION"
    CORRELATION_EXPOSURE = "CORRELATION_EXPOSURE"
    LIQUIDITY_TOO_LOW = "LIQUIDITY_TOO_LOW"
    POSITION_SIZE_TOO_LARGE = "POSITION_SIZE_TOO_LARGE"
    LEVERAGE_LIMIT = "LEVERAGE_LIMIT"
    GROSS_EXPOSURE_LIMIT = "GROSS_EXPOSURE_LIMIT"
    NET_EXPOSURE_LIMIT = "NET_EXPOSURE_LIMIT"
    VOLATILITY_LIMIT = "VOLATILITY_LIMIT"
    MARKET_STRESS = "MARKET_STRESS"
    INVALID_STOP = "INVALID_STOP"
    INVALID_ENTRY = "INVALID_ENTRY"
    INSUFFICIENT_CAPITAL = "INSUFFICIENT_CAPITAL"
    STALE_CONTEXT = "STALE_CONTEXT"
    MISSING_REQUIRED_CONTEXT = "MISSING_REQUIRED_CONTEXT"
    INVALID_TRADE_CANDIDATE = "INVALID_TRADE_CANDIDATE"
    RISK_CONFIGURATION_INVALID = "RISK_CONFIGURATION_INVALID"
    MAX_OPEN_POSITIONS = "MAX_OPEN_POSITIONS"
    MAX_ENTRIES_PER_DAY = "MAX_ENTRIES_PER_DAY"
    SESSION_CLOSED = "SESSION_CLOSED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True, slots=True)
class PositionRisk:
    """Risk and notional impact of one proposed position."""
    entry_price: float
    stop_price: float
    stop_distance: float
    risk_budget: float
    risk_per_unit: float
    quantity: float
    notional: float
    reward_risk_ratio: float | None = None

    def __post_init__(self) -> None:
        values = (
            self.entry_price, self.stop_price, self.stop_distance,
            self.risk_budget, self.risk_per_unit, self.quantity, self.notional,
        )
        if any(not isfinite(float(value)) for value in values):
            raise ValueError("PositionRisk values must be finite")
        if self.entry_price <= 0 or self.stop_price <= 0:
            raise ValueError("position prices must be positive")
        if self.stop_distance <= 0 or self.risk_per_unit <= 0:
            raise ValueError("risk distances must be positive")
        if self.quantity <= 0 or self.notional <= 0:
            raise ValueError("quantity and notional must be positive")
        if self.risk_budget < 0:
            raise ValueError("risk budget must be non-negative")
        if self.reward_risk_ratio is not None and (
            not isfinite(float(self.reward_risk_ratio))
            or self.reward_risk_ratio < 0
        ):
            raise ValueError("reward_risk_ratio must be non-negative and finite")


@dataclass(frozen=True, slots=True)
class PortfolioRiskState:
    """Point-in-time account and portfolio state."""
    timestamp: pd.Timestamp
    starting_equity: float
    equity: float
    daily_starting_equity: float | None = None
    available_cash: float
    reserved_capital: float = 0.0
    realized_pnl_today: float = 0.0
    unrealized_pnl_today: float = 0.0
    cumulative_pnl: float = 0.0
    peak_equity: float | None = None
    open_positions: int = 0
    entries_today: int = 0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    open_trade_risk: float = 0.0
    symbol_exposure: dict[str, float] = field(default_factory=dict)
    sector_exposure: dict[str, float] = field(default_factory=dict)
    symbol_risk: dict[str, float] = field(default_factory=dict)
    sector_risk: dict[str, float] = field(default_factory=dict)
    leverage: float = 0.0

    def __post_init__(self) -> None:
        if pd.Timestamp(self.timestamp).tzinfo is None:
            raise ValueError("portfolio timestamp must be timezone-aware")
        if self.starting_equity <= 0 or self.equity <= 0:
            raise ValueError("equity values must be positive")
        if self.daily_starting_equity is not None and self.daily_starting_equity <= 0:
            raise ValueError("daily_starting_equity must be positive when supplied")
        for name, value in (
            ("available_cash", self.available_cash),
            ("reserved_capital", self.reserved_capital),
            ("gross_exposure", self.gross_exposure),
            ("open_trade_risk", self.open_trade_risk),
            ("leverage", self.leverage),
        ):
            if not isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.open_positions < 0 or self.entries_today < 0:
            raise ValueError("position and entry counts must be non-negative")
        if self.peak_equity is not None and (
            not isfinite(float(self.peak_equity)) or self.peak_equity <= 0
        ):
            raise ValueError("peak_equity must be positive when supplied")
        for mapping_name, mapping in (
            ("symbol_exposure", self.symbol_exposure),
            ("sector_exposure", self.sector_exposure),
            ("symbol_risk", self.symbol_risk),
            ("sector_risk", self.sector_risk),
        ):
            for key, value in mapping.items():
                if not str(key).strip():
                    raise ValueError(f"{mapping_name} has an empty key")
                if not isfinite(float(value)) or float(value) < 0:
                    raise ValueError(f"{mapping_name} values must be non-negative")

    @property
    def daily_pnl(self) -> float:
        """Return current realized + unrealized P&L for the day."""
        return self.realized_pnl_today + self.unrealized_pnl_today

    @property
    def current_drawdown(self) -> float:
        """Return absolute drawdown from the current equity peak."""
        peak = self.peak_equity if self.peak_equity is not None else self.equity
        return max(0.0, peak - self.equity)


@dataclass(frozen=True, slots=True)
class MarketRiskContext:
    """Point-in-time market context consumed by Risk."""
    timestamp: pd.Timestamp
    session_open: pd.Timestamp
    session_close: pd.Timestamp
    is_market_open: bool = True
    market_regime: str | None = None
    volatility_regime: str | None = None
    volatility_value: float | None = None
    liquidity_score: float | None = None
    average_volume: float | None = None
    recent_volume: float | None = None
    sector: str | None = None
    correlation: float | None = None
    bid_ask_spread_bps: float | None = None
    stale_after_seconds: float = 300.0
    stress_flag: bool = False

    def __post_init__(self) -> None:
        timestamps = (
            pd.Timestamp(self.timestamp),
            pd.Timestamp(self.session_open),
            pd.Timestamp(self.session_close),
        )
        if any(ts.tzinfo is None for ts in timestamps):
            raise ValueError("market timestamps must be timezone-aware")
        if timestamps[2] <= timestamps[1]:
            raise ValueError("session_close must be after session_open")
        if self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        for name, value in (
            ("volatility_value", self.volatility_value),
            ("liquidity_score", self.liquidity_score),
            ("average_volume", self.average_volume),
            ("recent_volume", self.recent_volume),
            ("correlation", self.correlation),
            ("bid_ask_spread_bps", self.bid_ask_spread_bps),
        ):
            if value is not None and not isfinite(float(value)):
                raise ValueError(f"{name} must be finite when supplied")
        if self.average_volume is not None and self.average_volume < 0:
            raise ValueError("average_volume must be non-negative")
        if self.recent_volume is not None and self.recent_volume < 0:
            raise ValueError("recent_volume must be non-negative")


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Versioned deterministic Risk Engine policy."""
    policy_version: str = "risk_v1.0"
    risk_per_trade: float = 0.005
    max_daily_loss: float = 0.015
    max_drawdown: float = 0.10
    max_entries_per_day: int = 5
    max_open_positions: int = 3
    max_gross_exposure: float = 0.75
    max_net_exposure: float = 0.75
    max_leverage: float = 1.0
    max_symbol_exposure: float = 0.25
    max_sector_exposure: float = 0.40
    max_correlation_exposure: float = 0.60
    min_reward_risk: float = 1.50
    max_liquidity_participation: float = 0.10
    max_spread_bps: float | None = None
    stale_context_seconds: float = 300.0
    reduce_on_high_volatility: bool = False
    high_volatility_risk_multiplier: float = 1.0
    allow_missing_liquidity: bool = False
    require_market_open: bool = True

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("policy_version must not be empty")
        for name, value in (
            ("risk_per_trade", self.risk_per_trade),
            ("max_daily_loss", self.max_daily_loss),
            ("max_drawdown", self.max_drawdown),
            ("max_gross_exposure", self.max_gross_exposure),
            ("max_net_exposure", self.max_net_exposure),
            ("max_leverage", self.max_leverage),
            ("max_symbol_exposure", self.max_symbol_exposure),
            ("max_sector_exposure", self.max_sector_exposure),
            ("max_correlation_exposure", self.max_correlation_exposure),
            ("min_reward_risk", self.min_reward_risk),
            ("max_liquidity_participation", self.max_liquidity_participation),
            ("stale_context_seconds", self.stale_context_seconds),
            ("high_volatility_risk_multiplier", self.high_volatility_risk_multiplier),
        ):
            if not isfinite(float(value)) or float(value) < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.risk_per_trade > 1 or self.max_daily_loss > 1 or self.max_drawdown > 1:
            raise ValueError("risk proportion values must be <= 1")
        if self.max_entries_per_day < 0 or self.max_open_positions < 0:
            raise ValueError("count limits must be non-negative")
        if self.max_liquidity_participation > 1:
            raise ValueError("max_liquidity_participation must be <= 1")
        if self.max_spread_bps is not None and (
            not isfinite(float(self.max_spread_bps)) or self.max_spread_bps < 0
        ):
            raise ValueError("max_spread_bps must be non-negative")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Immutable and auditable Risk Engine output."""
    decision_id: str
    timestamp: pd.Timestamp
    symbol: str
    direction: CandidateDirection
    status: RiskDecisionStatus
    approved_quantity: float
    approved_notional: float
    planned_risk: float
    risk_per_unit: float
    reward_risk_ratio: float | None
    gross_exposure_before: float
    gross_exposure_after: float
    net_exposure_before: float
    net_exposure_after: float
    risk_utilization: float
    reason_codes: tuple[RiskReasonCode, ...]
    restrictions: tuple[str, ...]
    risk_policy_version: str
    candidate_policy_version: str
    created_at: pd.Timestamp
    provenance: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, ts in (("timestamp", self.timestamp), ("created_at", self.created_at)):
            if pd.Timestamp(ts).tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if not self.decision_id or not self.symbol.strip():
            raise ValueError("decision_id and symbol are required")
        values = (
            self.approved_quantity, self.approved_notional, self.planned_risk,
            self.risk_per_unit, self.gross_exposure_before, self.gross_exposure_after,
            self.net_exposure_before, self.net_exposure_after, self.risk_utilization,
        )
        if any(not isfinite(float(value)) for value in values):
            raise ValueError("RiskDecision numeric values must be finite")

        non_negative = (
            self.approved_quantity,
            self.approved_notional,
            self.planned_risk,
            self.risk_per_unit,
            self.gross_exposure_before,
            self.gross_exposure_after,
            self.risk_utilization,
        )
        if any(float(value) < 0 for value in non_negative):
            raise ValueError("RiskDecision non-negative fields cannot be negative")
        if not self.reason_codes:
            raise ValueError("every RiskDecision needs a reason code")
        if self.status is RiskDecisionStatus.REJECTED and (
            self.approved_quantity != 0 or self.approved_notional != 0
        ):
            raise ValueError("rejected decisions must carry zero approved exposure")

    @property
    def approved(self) -> bool:
        """Return whether execution may proceed downstream."""
        return self.status is not RiskDecisionStatus.REJECTED
