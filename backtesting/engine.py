"""AB-39 historical backtesting engine.

Replays historical decision-time rows through the existing trading
boundaries without introducing a second strategy or execution engine.

Causality:
    At timestamp T, only information available at T may influence
    the trading decision. Future rows are used only after they become
    the current replay timestamp and therefore cannot influence an
    earlier decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from backtesting.costs import CostConfig, TransactionCostModel
from backtesting.fills import FillConfig, FillModel
from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
    authorize_risk_decision,
)
from paper.runtime import PaperOrder, PaperTradingRuntime
from trading.paper.lifecycle import PaperTradeLifecycle, TradeOutcome
from trading.risk.engine import RiskEngine
from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.risk.pipeline import evaluate_strategy_candidate_risk
from trading.strategy.engine import StrategyEngine
from trading.strategy.models import (
    BaselineStrategyConfig,
    StrategyConfig,
    StrategyDecision,
    StrategyDirection,
    StrategyInput,
)


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Configuration for deterministic historical replay."""

    price_column: str = "close"
    quantity: float = 1.0
    max_holding_minutes: float = 60.0
    initial_equity: float = 100_000.0
    risk_enabled: bool = True

    def __post_init__(self) -> None:
        if not self.price_column:
            raise ValueError("price_column must not be empty")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive")

        if self.max_holding_minutes <= 0:
            raise ValueError("max_holding_minutes must be positive")

        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")


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


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Immutable result of one historical backtest run."""

    steps: tuple[BacktestStep, ...]
    outcomes: tuple[TradeOutcome, ...]

    @property
    def orders(self) -> tuple[PaperOrder, ...]:
        """Return all paper orders generated during the run."""
        return tuple(
            step.order
            for step in self.steps
            if step.order is not None
        )

    @property
    def completed_trades(self) -> int:
        """Return the number of completed trades."""
        return len(self.outcomes)

    @property
    def net_pnl(self) -> float:
        """Return aggregate net P&L from completed trades."""
        return sum(
            outcome.net_pnl
            for outcome in self.outcomes
        )


class HistoricalBacktestEngine:
    """Replay historical decision rows through existing trading boundaries."""

    def __init__(
        self,
        *,
        config: BacktestConfig | None = None,
        strategy_config: StrategyConfig | BaselineStrategyConfig | None = None,
        runtime: PaperTradingRuntime | None = None,
        lifecycle: PaperTradeLifecycle | None = None,
    ) -> None:
        self.config = config or BacktestConfig()
        self.strategy_engine = StrategyEngine(
            self._coerce_strategy_config(strategy_config)
        )
        self.risk_engine = RiskEngine()
        self.runtime = runtime or PaperTradingRuntime()
        self.lifecycle = lifecycle or PaperTradeLifecycle()

    @staticmethod
    def _coerce_strategy_config(
        config: StrategyConfig | BaselineStrategyConfig | None,
    ) -> StrategyConfig:
        """Normalize legacy baseline configuration callers."""
        if config is None:
            return StrategyConfig()
        if isinstance(config, StrategyConfig):
            return config
        if isinstance(config, BaselineStrategyConfig):
            return StrategyConfig(baseline=config)
        raise TypeError(
            "strategy_config must be StrategyConfig, BaselineStrategyConfig, or None"
        )

    def run(self, rows: pd.DataFrame) -> BacktestResult:
        """Run a deterministic chronological historical replay."""

        working = self._prepare_rows(rows)

        if working.empty:
            return BacktestResult(
                steps=(),
                outcomes=(),
            )

        steps: list[BacktestStep] = []
        session_date: object | None = None
        day_start_equity = self.config.initial_equity
        day_start_realized = 0.0
        trades_today = 0
        last_prices: dict[str, float] = {}

        # The final historical timestamp cannot support a new entry,
        # because there is no later observation available to evaluate
        # that trade's outcome.
        final_timestamp = working["timestamp"].max()

        for _, row in working.iterrows():
            timestamp = pd.Timestamp(row["timestamp"])
            symbol = str(row["symbol"]).upper()
            price = float(row[self.config.price_column])
            last_prices[symbol] = price

            # Expire an existing position before processing a new
            # decision at the current timestamp.
            self._close_expired_trade(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
            )

            realized_total, unrealized_pnl, gross_exposure = (
                self._risk_account_state(
                    last_prices=last_prices,
                )
            )
            equity = (
                self.config.initial_equity
                + realized_total
                + unrealized_pnl
            )

            current_date = timestamp.date()
            if session_date != current_date:
                session_date = current_date
                day_start_equity = equity
                day_start_realized = realized_total
                trades_today = 0

            daily_realized = realized_total - day_start_realized
            open_positions = len(self.lifecycle.open_symbols)
            symbol_already_open = (
                self._open_trade(symbol) is not None
            )

            strategy_input = self._strategy_input_from_row(row)
            strategy, _trace = self.strategy_engine.decide(
                strategy_input
            )

            liquidity_available = bool(
                row["liquidity_available"]
            ) if "liquidity_available" in row.index else True

            assessment = evaluate_strategy_candidate_risk(
                strategy,
                row,
                self.risk_engine,
                available_equity=equity,
                day_start_equity=day_start_equity,
                realized_pnl=daily_realized,
                unrealized_pnl=unrealized_pnl,
                open_positions=open_positions,
                trades_today=trades_today,
                gross_exposure=gross_exposure,
                symbol_already_open=symbol_already_open,
                liquidity_available=liquidity_available,
                risk_enabled=self.config.risk_enabled,
            )

            risk = assessment.decision
            authorization = authorize_risk_decision(risk)

            order: PaperOrder | None = None

            # Never open a new trade on the final historical observation.
            # There is no future bar available to evaluate its outcome.
            if (
                timestamp < final_timestamp
                and authorization.status
                is ExecutionAuthorizationStatus.AUTHORIZED
            ):
                position_size = assessment.position_size
                if position_size is None:
                    risk = RiskDecision(
                        timestamp=timestamp,
                        symbol=symbol,
                        status=RiskDecisionStatus.REJECTED,
                        strategy_direction=strategy.direction,
                        reason="Risk assessment did not produce a position size.",
                        risk_version="RISK-v1.0",
                    )
                    authorization = authorize_risk_decision(risk)
                else:
                    order = self._handle_authorized_decision(
                        authorization=authorization,
                        price=price,
                        quantity=position_size,
                    )
                    if order is not None and order.status.value == "FILLED":
                        trades_today += 1

            steps.append(
                BacktestStep(
                    timestamp=timestamp,
                    symbol=symbol,
                    price=price,
                    strategy=strategy,
                    risk=risk,
                    authorization=authorization,
                    order=order,
                )
            )

        # End-of-data is a deterministic historical exit condition.
        self._close_remaining_trades(working)

        return BacktestResult(
            steps=tuple(steps),
            outcomes=self.lifecycle.outcomes,
        )

    @staticmethod
    def _strategy_input_from_row(row: pd.Series) -> StrategyInput:
        """Build the centralized StrategyInput from one causal row."""
        required = {
            "timestamp",
            "symbol",
            "regime",
            "regime_probability",
            "vwap_distance_pct",
            "rvol_20",
            "higher_high",
            "higher_low",
            "lower_low",
            "lower_high",
        }
        missing = required.difference(row.index)
        if missing:
            raise ValueError(
                "backtest strategy row is missing required columns: "
                f"{sorted(missing)}"
            )

        feature_names = (
            "vwap_distance_pct",
            "rvol_20",
            "higher_high",
            "higher_low",
            "lower_low",
            "lower_high",
        )
        features = {name: row[name] for name in feature_names}

        return StrategyInput(
            timestamp=pd.Timestamp(row["timestamp"]),
            symbol=str(row["symbol"]),
            decision_features=features,
            regime=str(row["regime"]),
            regime_probability=float(row["regime_probability"]),
        )

    def _risk_account_state(
        self,
        *,
        last_prices: dict[str, float],
    ) -> tuple[float, float, float]:
        """Return realized P&L, unrealized P&L and gross exposure."""
        realized_total = sum(
            outcome.net_pnl
            for outcome in self.lifecycle.outcomes
        )
        unrealized = 0.0
        gross_exposure = 0.0

        for open_symbol in self.lifecycle.open_symbols:
            order = self.lifecycle.open_order(open_symbol)
            if order is None:
                continue

            mark = last_prices.get(open_symbol)
            if mark is None:
                raise ValueError(
                    f"missing causal mark price for open position {open_symbol}"
                )

            if order.direction is StrategyDirection.LONG:
                unrealized += (
                    mark - order.fill_price
                ) * order.quantity
            else:
                unrealized += (
                    order.fill_price - mark
                ) * order.quantity

            gross_exposure += mark * order.quantity

        return realized_total, unrealized, gross_exposure

    def _handle_authorized_decision(
        self,
        *,
        authorization: ExecutionAuthorization,
        price: float,
        quantity: float,
    ) -> PaperOrder | None:
        """Handle an approved decision while preserving one trade per symbol."""

        symbol = authorization.symbol.upper()
        existing = self._open_trade(symbol)

        if existing is not None:
            # Same-direction signal while already in the trade:
            # do not pyramid.
            if existing.direction is authorization.direction:
                return None

            # Opposite signal closes the existing position first.
            self._close_trade(
                symbol=symbol,
                timestamp=authorization.timestamp,
                price=price,
            )

        order = self.runtime.submit(
            authorization,
            price=price,
            quantity=quantity,
        )

        if order.status.value == "FILLED":
            self.lifecycle.open(order)

        return order

    def _close_expired_trade(
        self,
        *,
        symbol: str,
        timestamp: pd.Timestamp,
        price: float,
    ) -> None:
        """Close a trade once its configured holding period is reached."""

        order = self._open_trade(symbol)

        if order is None:
            return

        age = timestamp - order.timestamp
        maximum_age = timedelta(
            minutes=self.config.max_holding_minutes
        )

        if age >= maximum_age:
            self._close_trade(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
            )

    def _close_remaining_trades(
        self,
        rows: pd.DataFrame,
    ) -> None:
        """Close remaining trades at the final available price per symbol."""

        for symbol, group in rows.groupby(
            "symbol",
            sort=False,
        ):
            symbol = str(symbol).upper()

            order = self._open_trade(symbol)

            if order is None:
                continue

            final_row = group.iloc[-1]

            self._close_trade(
                symbol=symbol,
                timestamp=pd.Timestamp(final_row["timestamp"]),
                price=float(final_row[self.config.price_column]),
            )

    def _close_trade(
        self,
        *,
        symbol: str,
        timestamp: pd.Timestamp,
        price: float,
    ) -> TradeOutcome:
        """Close a trade using the configured deterministic exit model."""

        order = self._open_trade(symbol)
        if order is None:
            raise RuntimeError(f"no open trade exists for {symbol}")

        exit_direction = (
            StrategyDirection.SHORT
            if order.direction is StrategyDirection.LONG
            else StrategyDirection.LONG
        )

        fill = FillModel(
            FillConfig(slippage_bps=self.runtime.config.slippage_bps)
        ).fill(
            price=price,
            quantity=order.quantity,
            direction=exit_direction,
        )

        exit_fees = TransactionCostModel(
            CostConfig(brokerage_bps=self.runtime.config.fee_bps)
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
        )

    def _open_trade(
        self,
        symbol: str,
    ) -> PaperOrder | None:
        """Return the current lifecycle order for a symbol."""

        return self.lifecycle.open_order(symbol)

    def _prepare_rows(
        self,
        rows: pd.DataFrame,
    ) -> pd.DataFrame:
        """Validate and chronologically normalize historical rows."""

        if not isinstance(rows, pd.DataFrame):
            raise TypeError(
                "rows must be a pandas DataFrame"
            )

        if rows.empty:
            return rows.copy()

        required = {
            "timestamp",
            "symbol",
            self.config.price_column,
        }

        missing = required.difference(rows.columns)

        if missing:
            raise ValueError(
                "backtest rows are missing required columns: "
                f"{sorted(missing)}"
            )

        working = rows.copy()

        working["timestamp"] = pd.to_datetime(
            working["timestamp"],
            utc=True,
            errors="raise",
        )

        if working["timestamp"].isna().any():
            raise ValueError(
                "backtest timestamps must not be missing"
            )

        if working["symbol"].isna().any():
            raise ValueError(
                "backtest symbols must not be missing"
            )

        working["symbol"] = (
            working["symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        if (working["symbol"] == "").any():
            raise ValueError(
                "backtest symbols must not be empty"
            )

        prices = pd.to_numeric(
            working[self.config.price_column],
            errors="raise",
        )

        if prices.isna().any():
            raise ValueError(
                f"{self.config.price_column} must not contain missing values"
            )

        if (prices <= 0).any():
            raise ValueError(
                f"{self.config.price_column} must contain positive prices"
            )

        working[self.config.price_column] = prices

        return (
            working
            .sort_values(
                ["timestamp", "symbol"],
                kind="stable",
            )
            .reset_index(drop=True)
        )
