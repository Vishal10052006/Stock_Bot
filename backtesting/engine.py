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
from trading.risk.gate import (
    RiskDecision,
    evaluate_strategy_risk,
)
from trading.strategy.baseline import evaluate_row
from trading.strategy.models import (
    BaselineStrategyConfig,
    StrategyDecision,
)


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Configuration for deterministic historical replay."""

    price_column: str = "close"
    quantity: float = 1.0
    max_holding_minutes: float = 60.0
    risk_enabled: bool = True

    def __post_init__(self) -> None:
        if not self.price_column:
            raise ValueError("price_column must not be empty")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive")

        if self.max_holding_minutes <= 0:
            raise ValueError("max_holding_minutes must be positive")


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
        strategy_config: BaselineStrategyConfig | None = None,
        runtime: PaperTradingRuntime | None = None,
        lifecycle: PaperTradeLifecycle | None = None,
    ) -> None:
        self.config = config or BacktestConfig()
        self.strategy_config = (
            strategy_config or BaselineStrategyConfig()
        )
        self.runtime = runtime or PaperTradingRuntime()
        self.lifecycle = lifecycle or PaperTradeLifecycle()

    def run(self, rows: pd.DataFrame) -> BacktestResult:
        """Run a deterministic chronological historical replay."""

        working = self._prepare_rows(rows)

        if working.empty:
            return BacktestResult(
                steps=(),
                outcomes=(),
            )

        steps: list[BacktestStep] = []

        # The final historical timestamp cannot support a new entry,
        # because there is no later observation available to evaluate
        # that trade's outcome.
        final_timestamp = working["timestamp"].max()

        for _, row in working.iterrows():
            timestamp = pd.Timestamp(row["timestamp"])
            symbol = str(row["symbol"]).upper()
            price = float(row[self.config.price_column])

            # Expire an existing position before processing a new
            # decision at the current timestamp.
            self._close_expired_trade(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
            )

            strategy = evaluate_row(
                row,
                config=self.strategy_config,
            )

            risk = evaluate_strategy_risk(
                strategy,
                risk_enabled=self.config.risk_enabled,
            )

            authorization = authorize_risk_decision(risk)

            order: PaperOrder | None = None

            # Never open a new trade on the final historical observation.
            # There is no future bar available to evaluate its outcome.
            if (
                timestamp < final_timestamp
                and authorization.status
                is ExecutionAuthorizationStatus.AUTHORIZED
            ):
                order = self._handle_authorized_decision(
                    authorization=authorization,
                    price=price,
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
                )
            )

        # End-of-data is a deterministic historical exit condition.
        self._close_remaining_trades(working)

        return BacktestResult(
            steps=tuple(steps),
            outcomes=self.lifecycle.outcomes,
        )

    def _handle_authorized_decision(
        self,
        *,
        authorization: ExecutionAuthorization,
        price: float,
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
            quantity=self.config.quantity,
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

        open_records = getattr(
            self.lifecycle,
            "_open",
            {},
        )

        record = open_records.get(symbol)

        if record is None:
            return None

        order = record.get("order")

        if isinstance(order, PaperOrder):
            return order

        return None

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
