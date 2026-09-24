"""AB-35 deterministic paper decision loop.

Connects the existing Strategy -> Risk -> ExecutionAuthorization ->
PaperTradingRuntime boundaries for a chronological sequence of decision-time
rows. Prediction remains an upstream model output because the current
Phase 8 baseline strategy contract does not consume prediction probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import json

import pandas as pd

from experiments.paper_journal import PaperEvidenceJournal, PaperEvidenceRecord, persist_paper_decision_run
from execution.trading_execution import (
    ExecutionAuthorization,
    authorize_risk_decision,
)
from paper.runtime import PaperOrder, PaperTradingRuntime
from trading.risk.engine import RiskEngine
from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.risk.pipeline import evaluate_strategy_candidate_risk
from trading.strategy.engine import StrategyEngine
from trading.strategy.models import BaselineStrategyConfig, StrategyConfig, StrategyDecision, StrategyInput
from monitoring import (
    ExecutionMonitoringSnapshot,
    MonitoringRuntime,
    RiskMonitoringSnapshot,
    StrategyMonitoringSnapshot,
)


@dataclass(frozen=True, slots=True)
class PaperDecisionStep:
    """One auditable strategy -> risk -> authorization -> paper step."""

    strategy: StrategyDecision
    risk: RiskDecision
    authorization: ExecutionAuthorization
    order: PaperOrder | None


@dataclass(frozen=True, slots=True)
class PaperDecisionRun:
    """Immutable result of a chronological paper decision run."""

    steps: tuple[PaperDecisionStep, ...]

    @property
    def run_id(self) -> str:
        """Return a deterministic identity for this completed paper run."""
        payload = [_canonical_value(step) for step in self.steps]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def orders(self) -> tuple[PaperOrder, ...]:
        """Return only paper orders generated during the run."""
        return tuple(step.order for step in self.steps if step.order is not None)


class PaperDecisionLoop:
    """Run the existing downstream trading boundaries without broker I/O."""

    def __init__(
        self,
        *,
        runtime: PaperTradingRuntime | None = None,
        strategy_config: StrategyConfig | BaselineStrategyConfig | None = None,
        risk_enabled: bool = True,
        monitoring: MonitoringRuntime | None = None,
    ) -> None:
        self.runtime = runtime or PaperTradingRuntime()
        self.strategy_engine = StrategyEngine(
            self._coerce_strategy_config(strategy_config)
        )
        self.risk_engine = RiskEngine()
        self.risk_enabled = risk_enabled
        self.monitoring = monitoring or MonitoringRuntime()

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

    def run(
        self,
        rows: pd.DataFrame,
        *,
        price_column: str = "close",
        quantity: float = 1.0,
    ) -> PaperDecisionRun:
        """Process decision-time rows strictly in timestamp order.

        Rows are validated before execution. Every row produces exactly one
        strategy/risk/authorization step; only AUTHORIZED decisions create
        paper orders.
        """
        if not isinstance(rows, pd.DataFrame):
            raise TypeError("rows must be a pandas DataFrame")
        if rows.empty:
            return PaperDecisionRun(steps=())
        if price_column not in rows.columns:
            raise ValueError(f"rows must contain {price_column!r}")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if "timestamp" not in rows.columns:
            raise ValueError("rows must contain 'timestamp'")

        working = rows.copy()
        working["timestamp"] = pd.to_datetime(working["timestamp"], utc=True)
        working = working.sort_values(
            ["timestamp", "symbol"] if "symbol" in working.columns else ["timestamp"],
            kind="stable",
        ).reset_index(drop=True)

        steps: list[PaperDecisionStep] = []
        last_prices: dict[str, float] = {}
        session_date: object | None = None
        day_start_equity = self.runtime.config.initial_equity
        day_start_realized = self.runtime.realized_pnl
        trades_today = 0
        monitoring_decisions = 0
        monitoring_trades = 0
        monitoring_long_trades = 0
        monitoring_short_trades = 0
        monitoring_no_trade = 0
        monitoring_orders = 0
        monitoring_filled = 0
        monitoring_rejected = 0
        monitoring_slippage = 0.0

        for _, row in working.iterrows():
            price = float(row[price_column])
            symbol = str(row["symbol"]).upper()
            timestamp = pd.Timestamp(row["timestamp"])
            last_prices[symbol] = price

            equity, realized_total, unrealized_pnl, gross_exposure = (
                self.runtime.account_snapshot(last_prices)
            )

            current_date = timestamp.date()
            if session_date != current_date:
                session_date = current_date
                day_start_equity = equity
                day_start_realized = realized_total
                trades_today = 0

            daily_realized = realized_total - day_start_realized
            open_positions = len(self.runtime.positions)
            symbol_already_open = (
                self.runtime.position(symbol) is not None
            )

            strategy_input = self._strategy_input_from_row(row)
            strategy, _trace = self.strategy_engine.decide(strategy_input)

            monitoring_decisions += 1
            if strategy.direction.value == "NO_TRADE":
                monitoring_no_trade += 1
            elif strategy.direction.value == "LONG":
                monitoring_long_trades += 1
            elif strategy.direction.value == "SHORT":
                monitoring_short_trades += 1

            self.monitoring.observe_strategy(
                StrategyMonitoringSnapshot(
                    decisions=monitoring_decisions,
                    trades=monitoring_trades,
                    long_trades=monitoring_long_trades,
                    short_trades=monitoring_short_trades,
                    no_trade=monitoring_no_trade,
                    net_pnl=float(self.runtime.realized_pnl),
                )
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
                risk_enabled=self.risk_enabled,
            )
            risk = assessment.decision
            daily_monitoring_pnl = (
                float(equity - day_start_equity)
            )
            self.monitoring.observe_risk(
                RiskMonitoringSnapshot(
                    equity=float(equity),
                    daily_pnl=daily_monitoring_pnl,
                    open_positions=open_positions,
                    gross_exposure=float(gross_exposure),
                    daily_loss_limit=float(
                        day_start_equity * self.risk_engine.config.max_daily_loss
                    ),
                    max_open_positions=self.risk_engine.config.max_open_positions,
                    max_gross_exposure=self.risk_engine.config.max_gross_exposure,
                    risk_per_trade=self.risk_engine.config.risk_per_trade,
                    realized_pnl=float(realized_total - day_start_realized),
                    unrealized_pnl=float(unrealized_pnl),
                )
            )
            authorization = authorize_risk_decision(
                risk,
                approved_quantity=(
                    float(assessment.position_size)
                    if assessment.position_size is not None
                    else 0.0
                ),
                approved_notional=(
                    float(assessment.entry_price) * float(assessment.position_size)
                    if assessment.entry_price is not None and assessment.position_size is not None
                    else 0.0
                ),
                risk_decision_id=(
                    f"{risk.timestamp.isoformat()}:{risk.symbol}:{risk.risk_version}"
                ),
            )

            order = None
            monitoring_orders += 1
            if authorization.status.value == "AUTHORIZED":
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
                    order = self.runtime.submit(
                        authorization,
                        price=price,
                        quantity=position_size,
                    )
                    if order.status.value == "FILLED":
                        trades_today += 1

            if order is not None:
                if order.status.value == "FILLED":
                    monitoring_filled += 1
                    monitoring_trades += 1
                    monitoring_slippage += float(order.slippage_cost)
                else:
                    monitoring_rejected += 1
                self.monitoring.observe_execution(
                    ExecutionMonitoringSnapshot(
                        order_count=monitoring_orders,
                        filled_count=monitoring_filled,
                        rejected_count=monitoring_rejected,
                        total_slippage=monitoring_slippage,
                    )
                )
                self.monitoring.observe_strategy(
                    StrategyMonitoringSnapshot(
                        decisions=monitoring_decisions,
                        trades=monitoring_trades,
                        long_trades=monitoring_long_trades,
                        short_trades=monitoring_short_trades,
                        no_trade=monitoring_no_trade,
                        net_pnl=float(self.runtime.realized_pnl),
                    )
                )

            steps.append(
                PaperDecisionStep(
                    strategy=strategy,
                    risk=risk,
                    authorization=authorization,
                    order=order,
                )
            )

        return PaperDecisionRun(steps=tuple(steps))

    def run_and_persist_evidence(
        self,
        rows: pd.DataFrame,
        *,
        journal: PaperEvidenceJournal,
        price_column: str = "close",
        quantity: float = 1.0,
        fill_timestamps: dict[int, object] | None = None,
        false_signals: dict[int, bool] | None = None,
        equity_observations: dict[int, float] | None = None,
        calibration_outcomes: dict[int, float] | None = None,
        operational_events: int = 0,
        operational_errors: int = 0,
        stale_events: int = 0,
        evidence_version: str,
        dataset_version: str,
        code_version: str,
    ) -> tuple[PaperDecisionRun, PaperEvidenceRecord]:
        """Run paper decisions and persist evidence under the run's stable identity.

        Evidence that cannot be inferred safely remains explicit at the API
        boundary; this method does not synthesize latency, calibration,
        equity, false-signal, or operational observations.
        """
        run = self.run(rows, price_column=price_column, quantity=quantity)
        record = persist_paper_decision_run(
            run,
            journal=journal,
            source_run_id=run.run_id,
            fill_timestamps=fill_timestamps,
            false_signals=false_signals,
            equity_observations=equity_observations,
            calibration_outcomes=calibration_outcomes,
            operational_events=operational_events,
            operational_errors=operational_errors,
            stale_events=stale_events,
            evidence_version=evidence_version,
            dataset_version=dataset_version,
            code_version=code_version,
        )
        return run, record


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
                "paper strategy row is missing required columns: "
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


def _canonical_value(value: object) -> object:
    """Convert run output objects into deterministic JSON-compatible values."""
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            field.name: _canonical_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
