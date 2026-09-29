"""Paper position tracking and exit outcome engine.

Consumes causal 5-minute candles to manage open paper positions through their
lifecycle:
    Entry -> Mark (MAE/MFE) -> Stop/Target/Cutoff -> Completed TradeOutcome.

Adheres strictly to TRADING_SPECIFICATION.md:
1. Purely simulated paper fills (broker execution remains locked).
2. Conservative ambiguity resolution: if stop and target are breached on the
   same candle, the engine deterministically resolves to STOP_LOSS.
3. Intraday session closure: all open intraday cash positions are closed at or
   before market cutoff (15:15 IST).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Callable

import pandas as pd

from paper.runtime import PaperOrder, PaperOrderStatus
from trading.paper.lifecycle import TradeLifecycleStatus, TradeOutcome
from trading.strategy.models import StrategyDirection


class ExitReason(str, Enum):
    """Authoritative reason for paper trade closure."""

    TARGET = "TARGET"
    STOP_LOSS = "STOP_LOSS"
    SESSION_CLOSE = "SESSION_CLOSE"
    MAX_HOLDING_TIME = "MAX_HOLDING_TIME"
    SIGNAL_REVERSAL = "SIGNAL_REVERSAL"
    RISK_SHUTDOWN = "RISK_SHUTDOWN"
    MANUAL = "MANUAL"


@dataclass
class PaperPosition:
    """Active open paper position tracked against incoming candles."""

    trade_id: str
    symbol: str
    direction: StrategyDirection
    entry_time: pd.Timestamp
    fill_price: float
    requested_price: float
    quantity: float
    stop_price: float
    target_price: float
    entry_fees: float = 0.0
    entry_slippage_cost: float = 0.0
    strategy_version: str = "STRAT-v1.0"
    model_version: str | None = None
    risk_version: str | None = None
    regime: str | None = None
    mae: float = 0.0
    mfe: float = 0.0
    bars_held: int = 0

    def __post_init__(self) -> None:
        self.entry_time = pd.Timestamp(self.entry_time)
        if self.entry_time.tzinfo is None:
            raise ValueError("entry_time must be timezone-aware")
        if self.fill_price <= 0 or self.requested_price <= 0:
            raise ValueError("prices must be positive")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.stop_price <= 0 or self.target_price <= 0:
            raise ValueError("stop and target prices must be positive")


class PaperExitEngine:
    """Evaluate and close open paper positions against sequential market candles."""

    def __init__(
        self,
        *,
        fee_bps: float = 5.0,
        slippage_bps: float = 2.0,
        max_holding_bars: int = 75,
        session_cutoff_time: str = "15:15",
    ) -> None:
        if fee_bps < 0 or slippage_bps < 0:
            raise ValueError("fee_bps and slippage_bps must be non-negative")
        if max_holding_bars <= 0:
            raise ValueError("max_holding_bars must be positive")

        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.max_holding_bars = max_holding_bars
        self.session_cutoff_hour = int(session_cutoff_time.split(":")[0])
        self.session_cutoff_minute = int(session_cutoff_time.split(":")[1])

        self._open_positions: dict[str, PaperPosition] = {}
        self._completed_outcomes: list[TradeOutcome] = []
        self._exit_reasons: dict[str, ExitReason] = {}

    @property
    def completed_outcomes(self) -> tuple[TradeOutcome, ...]:
        """Return completed outcomes in chronological close order."""
        return tuple(self._completed_outcomes)

    @property
    def exit_reasons(self) -> dict[str, ExitReason]:
        """Return mapping of trade_id to ExitReason."""
        return dict(self._exit_reasons)

    def has_open_position(self, symbol: str) -> bool:
        """Check if an open position exists for the given symbol."""
        return symbol.strip().upper() in self._open_positions

    def get_open_position(self, symbol: str) -> PaperPosition | None:
        """Retrieve the active position for a symbol if open."""
        return self._open_positions.get(symbol.strip().upper())

    def all_open_positions(self) -> tuple[PaperPosition, ...]:
        """Return all currently open positions."""
        return tuple(self._open_positions.values())

    def open_position(
        self,
        order: PaperOrder,
        *,
        stop_price: float,
        target_price: float,
        trade_id: str | None = None,
        strategy_version: str = "STRAT-v1.0",
        model_version: str | None = None,
        risk_version: str | None = None,
        regime: str | None = None,
    ) -> PaperPosition:
        """Register a filled paper order into the active position tracker."""
        if not isinstance(order, PaperOrder):
            raise TypeError("order must be a PaperOrder")
        if order.status is not PaperOrderStatus.FILLED:
            raise ValueError("only FILLED paper orders can open a position")

        symbol = order.symbol.strip().upper()
        if symbol in self._open_positions:
            raise ValueError(f"position already open for {symbol}")

        resolved_trade_id = trade_id or f"{order.reason}:{symbol}:{pd.Timestamp(order.timestamp).strftime('%Y%m%d%H%M%S')}"
        position = PaperPosition(
            trade_id=resolved_trade_id,
            symbol=symbol,
            direction=order.direction,
            entry_time=order.timestamp,
            fill_price=order.fill_price,
            requested_price=order.requested_price,
            quantity=order.quantity,
            stop_price=stop_price,
            target_price=target_price,
            entry_fees=order.fees,
            entry_slippage_cost=order.slippage_cost,
            strategy_version=strategy_version,
            model_version=model_version,
            risk_version=risk_version,
            regime=regime,
        )
        self._open_positions[symbol] = position
        return position

    def process_candle(
        self,
        candle: Any,
        *,
        force_session_close: bool = False,
    ) -> list[TradeOutcome]:
        """Process one causal 5-minute candle against open positions.

        Accepts any candle object or dict with symbol, timestamp, open, high, low, close.
        Returns a list of TradeOutcome instances closed by this candle.
        """
        symbol = str(getattr(candle, "symbol", None) or candle["symbol"]).strip().upper()
        position = self._open_positions.get(symbol)
        if position is None:
            return []

        timestamp = pd.Timestamp(getattr(candle, "timestamp", None) or candle["timestamp"])
        open_p = float(getattr(candle, "open", None) if hasattr(candle, "open") else candle["open"])
        high_p = float(getattr(candle, "high", None) if hasattr(candle, "high") else candle["high"])
        low_p = float(getattr(candle, "low", None) if hasattr(candle, "low") else candle["low"])
        close_p = float(getattr(candle, "close", None) if hasattr(candle, "close") else candle["close"])

        if timestamp < position.entry_time:
            raise ValueError("candle timestamp cannot precede position entry time")

        position.bars_held += 1

        # 1. Update MAE and MFE using price extremes
        if position.direction is StrategyDirection.LONG:
            favorable_move = high_p - position.fill_price
            adverse_move = low_p - position.fill_price
        else:
            favorable_move = position.fill_price - low_p
            adverse_move = position.fill_price - high_p

        position.mfe = max(position.mfe, favorable_move * position.quantity)
        position.mae = min(position.mae, adverse_move * position.quantity)

        # 2. Check trigger conditions
        target_hit = False
        stop_hit = False

        if position.direction is StrategyDirection.LONG:
            target_hit = high_p >= position.target_price
            stop_hit = low_p <= position.stop_price
        else:
            target_hit = low_p <= position.target_price
            stop_hit = high_p >= position.stop_price

        # Check intraday session cutoff (NSE 15:15 IST)
        time_cutoff_hit = force_session_close or (
            timestamp.hour > self.session_cutoff_hour
            or (timestamp.hour == self.session_cutoff_hour and timestamp.minute >= self.session_cutoff_minute)
        )
        max_bars_hit = position.bars_held >= self.max_holding_bars

        # 3. Determine Exit Execution
        exit_price: float
        reason: ExitReason

        if target_hit and stop_hit:
            # Conservative Same-Candle Ambiguity Resolution:
            # When both levels are touched within the same bar, assume stop loss occurred first.
            exit_price = position.stop_price
            reason = ExitReason.STOP_LOSS
        elif stop_hit:
            exit_price = position.stop_price
            reason = ExitReason.STOP_LOSS
        elif target_hit:
            exit_price = position.target_price
            reason = ExitReason.TARGET
        elif time_cutoff_hit:
            exit_price = close_p
            reason = ExitReason.SESSION_CLOSE
        elif max_bars_hit:
            exit_price = close_p
            reason = ExitReason.MAX_HOLDING_TIME
        else:
            # Position remains open
            return []

        # 4. Finalize Trade Closure
        outcome = self._close_position(
            position,
            exit_time=timestamp,
            exit_price=exit_price,
            reason=reason,
        )
        del self._open_positions[symbol]
        self._completed_outcomes.append(outcome)
        self._exit_reasons[position.trade_id] = reason
        return [outcome]

    def close_all(
        self,
        *,
        timestamp: pd.Timestamp,
        price_lookup: Callable[[str], float] | Mapping[str, float] | None = None,
        reason: ExitReason = ExitReason.SESSION_CLOSE,
    ) -> list[TradeOutcome]:
        """Gracefully close all open positions at current market prices."""
        timestamp = pd.Timestamp(timestamp)
        outcomes: list[TradeOutcome] = []

        symbols = list(self._open_positions.keys())
        for symbol in symbols:
            position = self._open_positions[symbol]
            if callable(price_lookup):
                exit_price = float(price_lookup(symbol))
            elif isinstance(price_lookup, Mapping) and symbol in price_lookup:
                exit_price = float(price_lookup[symbol])
            else:
                exit_price = position.fill_price

            outcome = self._close_position(
                position,
                exit_time=timestamp,
                exit_price=exit_price,
                reason=reason,
            )
            del self._open_positions[symbol]
            self._completed_outcomes.append(outcome)
            self._exit_reasons[position.trade_id] = reason
            outcomes.append(outcome)

        return outcomes

    def _close_position(
        self,
        position: PaperPosition,
        *,
        exit_time: pd.Timestamp,
        exit_price: float,
        reason: ExitReason,
    ) -> TradeOutcome:
        """Compute execution costs, net P&L and create immutable TradeOutcome."""
        adverse_slip = self.slippage_bps / 10_000.0
        fee_rate = self.fee_bps / 10_000.0

        if position.direction is StrategyDirection.LONG:
            actual_exit_price = exit_price * (1.0 - adverse_slip)
            unit_gross = exit_price - position.requested_price
        else:
            actual_exit_price = exit_price * (1.0 + adverse_slip)
            unit_gross = position.requested_price - exit_price

        gross_pnl = unit_gross * position.quantity
        exit_fee = actual_exit_price * position.quantity * fee_rate
        exit_slip_cost = abs(exit_price - actual_exit_price) * position.quantity

        total_fees = position.entry_fees + exit_fee
        total_slippage = position.entry_slippage_cost + exit_slip_cost
        net_pnl = gross_pnl - total_fees - total_slippage

        holding_minutes = max(1.0, (exit_time - position.entry_time).total_seconds() / 60.0)

        return TradeOutcome(
            symbol=position.symbol,
            direction=position.direction,
            entry_time=position.entry_time,
            exit_time=exit_time,
            entry_price=position.fill_price,
            exit_price=actual_exit_price,
            quantity=position.quantity,
            gross_pnl=gross_pnl,
            fees=total_fees,
            slippage_cost=total_slippage,
            net_pnl=net_pnl,
            holding_minutes=holding_minutes,
            mae=position.mae,
            mfe=position.mfe,
            status=TradeLifecycleStatus.CLOSED,
        )


__all__ = [
    "ExitReason",
    "PaperExitEngine",
    "PaperPosition",
]
