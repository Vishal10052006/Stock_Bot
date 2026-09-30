"""Deterministic historical backtesting engine.

Replay boundary:
    Strategy -> Candidate -> Risk Engine -> Authorization -> Broker Simulator

All decisions are causal. Existing positions are managed before the current
bar can create a new position, and the final available observation cannot
open a new trade.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import math

import pandas as pd

from backtesting.broker_simulator import BrokerSimulator
from backtesting.fills import FillConfig, FillModel
from backtesting.costs import CostConfig, TransactionCostModel
from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
    authorize_risk_decision,
)
from paper.runtime import PaperOrder, PaperTradingRuntime
from trading.paper.lifecycle import PaperTradeLifecycle, TradeOutcome
from trading.risk.engine import RiskConfig, RiskEngine
from trading.risk.gate import RiskDecision
from trading.risk.pipeline import evaluate_strategy_candidate_risk
from trading.signals.models import CandidateConfig
from trading.strategy.engine import StrategyEngine
from trading.strategy.models import (
    BaselineStrategyConfig,
    StrategyDecision,
    StrategyDirection,
    StrategyInput,
)
from utils.fingerprint import artifact_fingerprint


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Deterministic historical replay and exit policy."""

    price_column: str = "close"
    quantity: float = 1.0
    max_holding_minutes: float = 60.0
    risk_enabled: bool = True
    starting_equity: float = 100_000.0
    target_reward_risk: float = 1.50
    partial_exit_fraction: float = 0.50
    quantity_step: float = 1.0
    candidate_config: CandidateConfig = CandidateConfig()

    def __post_init__(self) -> None:
        if not self.price_column:
            raise ValueError("price_column must not be empty")
        values = (
            self.quantity,
            self.max_holding_minutes,
            self.starting_equity,
            self.target_reward_risk,
            self.partial_exit_fraction,
            self.quantity_step,
        )
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("backtest configuration values must be finite")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.max_holding_minutes <= 0:
            raise ValueError("max_holding_minutes must be positive")
        if self.starting_equity <= 0:
            raise ValueError("starting_equity must be positive")
        if self.target_reward_risk <= 0:
            raise ValueError("target_reward_risk must be positive")
        if not 0 < self.partial_exit_fraction <= 1:
            raise ValueError("partial_exit_fraction must be in (0, 1]")
        if self.quantity_step <= 0:
            raise ValueError("quantity_step must be positive")


@dataclass(frozen=True, slots=True)
class BacktestStep:
    """Auditable result of one historical decision-time row."""

    timestamp: pd.Timestamp
    symbol: str
    price: float
    strategy: StrategyDecision
    risk: RiskDecision
    authorization: ExecutionAuthorization
    order: PaperOrder | None
    target_price: float | None = None
    stop_price: float | None = None


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Immutable result of one historical backtest run."""

    steps: tuple[BacktestStep, ...]
    outcomes: tuple[TradeOutcome, ...]

    @property
    def fingerprint(self) -> str:
        return artifact_fingerprint(self)

    @property
    def orders(self) -> tuple[PaperOrder, ...]:
        return tuple(step.order for step in self.steps if step.order is not None)

    @property
    def completed_trades(self) -> int:
        return len(self.outcomes)

    @property
    def net_pnl(self) -> float:
        return sum(outcome.net_pnl for outcome in self.outcomes)


class HistoricalBacktestEngine:
    """Replay historical rows through the existing trading authorities."""

    def __init__(
        self,
        *,
        config: BacktestConfig | None = None,
        strategy_config: BaselineStrategyConfig | None = None,
        runtime: PaperTradingRuntime | None = None,
        broker: BrokerSimulator | None = None,
        lifecycle: PaperTradeLifecycle | None = None,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        self.config = config or BacktestConfig()
        self.strategy_engine = StrategyEngine(
            StrategyEngine.coerce_config(strategy_config)
        )
        if broker is not None and runtime is not None:
            raise ValueError("provide either broker or runtime, not both")
        self.broker = broker or BrokerSimulator(runtime=runtime)
        self.runtime = self.broker.runtime
        self.lifecycle = lifecycle or PaperTradeLifecycle()
        self.risk_engine = risk_engine or RiskEngine(
            config=RiskConfig(
                target_multiple_r=self.config.target_reward_risk,
                quantity_step=self.config.quantity_step,
            )
        )
        self._trade_levels: dict[str, dict[str, float]] = {}
        self._last_marks: dict[str, float] = {}
        self._day_start_equity = self.config.starting_equity
        self._active_day: object | None = None

    def run(self, rows: pd.DataFrame) -> BacktestResult:
        working = self._prepare_rows(rows)
        if working.empty:
            return BacktestResult(steps=(), outcomes=())

        steps: list[BacktestStep] = []
        session_end_rows = self._session_end_rows(working)
        final_timestamp = working["timestamp"].max()

        for _, row in working.iterrows():
            timestamp = pd.Timestamp(row["timestamp"])
            symbol = str(row["symbol"]).upper()
            price = float(row[self.config.price_column])

            self._manage_open_trade(row, timestamp)
            self._last_marks[symbol] = price
            self._close_expired_trade(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
            )

            session_end = (symbol, timestamp) in session_end_rows
            if session_end and self._open_trade(symbol) is not None:
                self._close_trade(
                    symbol=symbol,
                    timestamp=timestamp,
                    price=price,
                )
                self._trade_levels.pop(symbol, None)

            strategy_input = self._strategy_input_from_row(
                row,
                timestamp=timestamp,
                symbol=symbol,
            )
            strategy, _trace = self.strategy_engine.decide(strategy_input)

            state = self._portfolio_state(
                timestamp=timestamp,
                symbol=symbol,
            )
            assessment = evaluate_strategy_candidate_risk(
                strategy,
                row,
                self.risk_engine,
                available_equity=float(state["equity"]),
                day_start_equity=float(state["day_start_equity"]),
                realized_pnl=float(state["realized_pnl"]),
                unrealized_pnl=float(state["unrealized_pnl"]),
                open_positions=int(state["open_positions"]),
                trades_today=int(state["trades_today"]),
                gross_exposure=float(state["gross_exposure"]),
                symbol_already_open=bool(state["symbol_already_open"]),
                liquidity_available=bool(state["liquidity_available"]),
                risk_enabled=self.config.risk_enabled,
                candidate_config=self.config.candidate_config,
            )
            risk = assessment.decision

            authorization = authorize_risk_decision(
                risk,
                approved_quantity=(
                    float(assessment.position_size)
                    if assessment.position_size is not None
                    else 0.0
                ),
                approved_notional=(
                    float(assessment.entry_price)
                    * float(assessment.position_size)
                    if assessment.entry_price is not None
                    and assessment.position_size is not None
                    else 0.0
                ),
                risk_decision_id=(
                    f"{risk.timestamp.isoformat()}:{risk.symbol}:"
                    f"{risk.risk_version}"
                ),
            )

            order: PaperOrder | None = None
            if (
                not session_end
                and timestamp < final_timestamp
                and authorization.status is ExecutionAuthorizationStatus.AUTHORIZED
            ):
                order = self._handle_authorized_decision(
                    authorization=authorization,
                    price=price,
                    stop_price=assessment.stop_price,
                    target_price=assessment.target_price,
                )

            steps.append(
                BacktestStep(
                    timestamp=timestamp,
                    symbol=symbol,
                    price=price,
                    strategy=strategy,
                    risk=risk,
                    authorization=authorization,
                    order=order,
                    target_price=assessment.target_price,
                    stop_price=assessment.stop_price,
                )
            )

        self._close_remaining_trades(working)
        return BacktestResult(
            steps=tuple(steps),
            outcomes=self.lifecycle.outcomes,
        )

    @staticmethod
    def _strategy_input_from_row(
        row: pd.Series,
        *,
        timestamp: pd.Timestamp,
        symbol: str,
    ) -> StrategyInput:
        required = (
            "vwap_distance_pct",
            "rvol_20",
            "higher_high",
            "higher_low",
            "lower_low",
            "lower_high",
        )
        return StrategyInput(
            timestamp=timestamp,
            symbol=symbol,
            decision_features={column: row[column] for column in required},
            regime=str(row["regime"]),
            regime_probability=float(row["regime_probability"]),
        )

    def _portfolio_state(
        self,
        *,
        timestamp: pd.Timestamp,
        symbol: str,
    ) -> dict[str, object]:
        day = timestamp.tz_convert("Asia/Kolkata").date()
        if self._active_day != day:
            self._active_day = day
            self._day_start_equity = self._current_equity()

        open_records = self.lifecycle._open
        gross = 0.0
        unrealized = 0.0

        for open_symbol, record in open_records.items():
            order = record.get("order")
            if not isinstance(order, PaperOrder):
                continue
            quantity = float(record.get("quantity", order.quantity))
            mark = float(self._last_marks.get(open_symbol, order.fill_price))
            gross += quantity * mark
            move = (
                mark - order.fill_price
                if order.direction is StrategyDirection.LONG
                else order.fill_price - mark
            )
            unrealized += move * quantity
            unrealized -= float(record.get("entry_fees", 0.0))

        realized_total = sum(
            outcome.net_pnl for outcome in self.lifecycle.outcomes
        )
        equity = max(
            1e-9,
            self.config.starting_equity + realized_total + unrealized,
        )

        realized_today = sum(
            outcome.net_pnl
            for outcome in self.lifecycle.outcomes
            if outcome.exit_time.tz_convert("Asia/Kolkata").date() == day
        )
        trades_today = sum(
            1
            for order in self.broker.journal
            if order.status.value == "FILLED"
            and order.timestamp.tz_convert("Asia/Kolkata").date() == day
        )

        return {
            "equity": equity,
            "day_start_equity": self._day_start_equity,
            "realized_pnl": realized_today,
            "unrealized_pnl": unrealized,
            "open_positions": len(open_records),
            "trades_today": trades_today,
            "gross_exposure": gross,
            "symbol_already_open": (
                symbol.upper()
                in {str(item).upper() for item in open_records}
            ),
            "liquidity_available": True,
        }

    def _current_equity(self) -> float:
        return max(
            1e-9,
            self.config.starting_equity
            + sum(outcome.net_pnl for outcome in self.lifecycle.outcomes),
        )

    def _handle_authorized_decision(
        self,
        *,
        authorization: ExecutionAuthorization,
        price: float,
        stop_price: float | None,
        target_price: float | None,
    ) -> PaperOrder | None:
        symbol = authorization.symbol.upper()
        existing = self._open_trade(symbol)

        if existing is not None:
            if existing.direction is authorization.direction:
                return None
            self._close_trade(
                symbol=symbol,
                timestamp=authorization.timestamp,
                price=price,
            )

        if authorization.approved_quantity <= 0:
            raise ValueError("authorized quantity must be positive")

        order = self.broker.submit(
            authorization,
            price=price,
            quantity=authorization.approved_quantity,
        )

        if order.status.value == "FILLED":
            self.lifecycle.open(order)
            if stop_price is not None and target_price is not None:
                self._trade_levels[symbol] = {
                    "stop": float(stop_price),
                    "target": float(target_price),
                }

        return order

    def _manage_open_trade(
        self,
        row: pd.Series,
        timestamp: pd.Timestamp,
    ) -> None:
        symbol = str(row["symbol"]).upper()
        order = self._open_trade(symbol)
        if order is None:
            return

        close_price = float(row["close"])
        self.lifecycle.mark(symbol, timestamp=timestamp, price=close_price)
        levels = self._trade_levels.get(symbol)
        if levels is None:
            return

        high = float(row.get("high", close_price))
        low = float(row.get("low", close_price))
        if high <= 0 or low <= 0 or low > high:
            raise ValueError(
                "historical high/low prices must be positive and ordered"
            )

        stop = levels["stop"]
        target = levels["target"]

        if order.direction is StrategyDirection.LONG:
            stop_hit = low <= stop
            target_hit = high >= target
        else:
            stop_hit = high >= stop
            target_hit = low <= target

        # Conservative OHLC ambiguity rule: stop takes precedence.
        if stop_hit:
            self._close_trade(
                symbol=symbol,
                timestamp=timestamp,
                price=stop,
            )
            self._trade_levels.pop(symbol, None)
            return

        if target_hit:
            quantity = (
                int(
                    order.quantity
                    * self.config.partial_exit_fraction
                    / self.config.quantity_step
                )
                * self.config.quantity_step
            )
            if quantity <= 0 or quantity >= order.quantity:
                self._close_trade(
                    symbol=symbol,
                    timestamp=timestamp,
                    price=target,
                )
                self._trade_levels.pop(symbol, None)
                return

            self._close_partial_trade(
                symbol=symbol,
                timestamp=timestamp,
                price=target,
                quantity=quantity,
            )
            levels["stop"] = order.fill_price
            levels["target"] = (
                float("inf")
                if order.direction is StrategyDirection.LONG
                else -float("inf")
            )

    def _close_partial_trade(
        self,
        *,
        symbol: str,
        timestamp: pd.Timestamp,
        price: float,
        quantity: float,
    ) -> TradeOutcome:
        order = self._open_trade(symbol)
        if order is None:
            raise RuntimeError(f"no open trade exists for {symbol}")

        direction = (
            StrategyDirection.SHORT
            if order.direction is StrategyDirection.LONG
            else StrategyDirection.LONG
        )
        fill = FillModel(
            FillConfig(
                slippage_bps=self.runtime.config.slippage_bps,
            )
        ).fill(
            price=price,
            quantity=quantity,
            direction=direction,
        )
        exit_fees = TransactionCostModel(
            CostConfig(
                brokerage_bps=self.runtime.config.fee_bps,
            )
        ).calculate(
            price=fill.fill_price,
            quantity=quantity,
        ).total

        return self.lifecycle.close_partial(
            symbol,
            timestamp=timestamp,
            price=fill.fill_price,
            quantity=quantity,
            exit_fees=exit_fees,
            exit_slippage_cost=fill.slippage_cost,
            reference_price=price,
        )

    def _close_expired_trade(
        self,
        *,
        symbol: str,
        timestamp: pd.Timestamp,
        price: float,
    ) -> None:
        order = self._open_trade(symbol)
        if order is None:
            return
        if timestamp - order.timestamp >= timedelta(
            minutes=self.config.max_holding_minutes
        ):
            self._close_trade(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
            )
            self._trade_levels.pop(symbol, None)

    @staticmethod
    def _session_end_rows(rows: pd.DataFrame) -> set[tuple[str, pd.Timestamp]]:
        indexed = rows.assign(
            _ist_day=rows["timestamp"].dt.tz_convert("Asia/Kolkata").dt.date,
            _symbol=rows["symbol"].astype(str).str.upper(),
        )
        return {
            (str(symbol).upper(), pd.Timestamp(timestamp))
            for (symbol, _day), timestamp in indexed.groupby(
                ["_symbol", "_ist_day"],
                sort=False,
            )["timestamp"].max().items()
        }

    def _close_remaining_trades(self, rows: pd.DataFrame) -> None:
        for symbol, group in rows.groupby("symbol", sort=False):
            symbol = str(symbol).upper()
            if self._open_trade(symbol) is None:
                continue
            final_row = group.iloc[-1]
            self._close_trade(
                symbol=symbol,
                timestamp=pd.Timestamp(final_row["timestamp"]),
                price=float(final_row[self.config.price_column]),
            )
            self._trade_levels.pop(symbol, None)

    def _close_trade(
        self,
        *,
        symbol: str,
        timestamp: pd.Timestamp,
        price: float,
    ) -> TradeOutcome:
        order = self._open_trade(symbol)
        if order is None:
            raise RuntimeError(f"no open trade exists for {symbol}")

        direction = (
            StrategyDirection.SHORT
            if order.direction is StrategyDirection.LONG
            else StrategyDirection.LONG
        )
        fill = FillModel(
            FillConfig(
                slippage_bps=self.runtime.config.slippage_bps,
            )
        ).fill(
            price=price,
            quantity=order.quantity,
            direction=direction,
        )
        exit_fees = TransactionCostModel(
            CostConfig(
                brokerage_bps=self.runtime.config.fee_bps,
            )
        ).calculate(
            price=fill.fill_price,
            quantity=order.quantity,
        ).total

        return self.lifecycle.close(
            symbol,
            timestamp=timestamp,
            price=fill.fill_price,
            exit_fees=exit_fees,
            exit_slippage_cost=fill.slippage_cost,
            reference_price=price,
        )

    def _open_trade(self, symbol: str) -> PaperOrder | None:
        record = self.lifecycle._open.get(symbol)
        if record is None:
            return None
        order = record.get("order")
        if not isinstance(order, PaperOrder):
            return None

        quantity = float(record.get("quantity", order.quantity))
        if quantity == order.quantity:
            return order

        return PaperOrder(
            timestamp=order.timestamp,
            symbol=order.symbol,
            direction=order.direction,
            requested_price=order.requested_price,
            fill_price=order.fill_price,
            quantity=quantity,
            status=order.status,
            fees=float(record.get("entry_fees", order.fees)),
            slippage_cost=float(
                record.get("entry_slippage_cost", order.slippage_cost)
            ),
            reason=order.reason,
        )

    @staticmethod
    def _prepare_rows(rows: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(rows, pd.DataFrame):
            raise TypeError("rows must be a pandas DataFrame")
        if rows.empty:
            return rows.copy()

        required = {
            "timestamp",
            "symbol",
            "close",
            "regime",
            "regime_probability",
            "vwap_distance_pct",
            "rvol_20",
            "higher_high",
            "higher_low",
            "lower_low",
            "lower_high",
        }
        missing = required.difference(rows.columns)
        if missing:
            raise ValueError(
                "backtest rows are missing required columns: "
                f"{sorted(missing)}"
            )

        working = rows.copy(deep=True)
        working["timestamp"] = pd.to_datetime(
            working["timestamp"],
            utc=True,
            errors="raise",
        )
        if working["timestamp"].isna().any():
            raise ValueError("backtest timestamps must not be missing")
        if working["symbol"].isna().any():
            raise ValueError("backtest symbols must not be missing")

        symbols = working["symbol"].astype(str).str.strip().str.upper()
        if symbols.eq("").any():
            raise ValueError("backtest symbols must not be empty")
        working["symbol"] = symbols

        for column in ("close",):
            values = pd.to_numeric(working[column], errors="coerce")
            if values.isna().any() or (values <= 0).any():
                raise ValueError(
                    f"backtest {column} prices must be positive and numeric"
                )

        if "high" in working.columns and "low" in working.columns:
            high = pd.to_numeric(working["high"], errors="coerce")
            low = pd.to_numeric(working["low"], errors="coerce")
            if high.isna().any() or low.isna().any():
                raise ValueError("backtest high/low prices must be numeric")
            if (high <= 0).any() or (low <= 0).any():
                raise ValueError("backtest high/low prices must be positive")
            if (high < low).any():
                raise ValueError("backtest high prices must be >= low prices")

        if "volume" in working.columns:
            volume = pd.to_numeric(working["volume"], errors="coerce")
            if volume.isna().any() or (volume <= 0).any():
                raise ValueError(
                    "backtest volume must be positive when provided"
                )

        if working.duplicated(
            subset=["symbol", "timestamp"],
            keep=False,
        ).any():
            raise ValueError(
                "backtest rows contain duplicate symbol/timestamp decisions"
            )

        return working.sort_values(
            ["timestamp", "symbol"],
            kind="stable",
        ).reset_index(drop=True)
