"""AB-35 deterministic paper decision loop.

Connects the existing Strategy -> Risk -> ExecutionAuthorization ->
PaperTradingRuntime boundaries for a chronological sequence of decision-time
rows. Prediction remains an upstream model output because the current
Phase 8 baseline strategy contract does not consume prediction probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from execution.trading_execution import (
    ExecutionAuthorization,
    authorize_risk_decision,
)
from paper.runtime import PaperOrder, PaperTradingRuntime
from trading.risk.gate import RiskDecision, evaluate_strategy_risk
from trading.strategy.engine import StrategyEngine
from trading.strategy.models import BaselineStrategyConfig, StrategyConfig, StrategyDecision, StrategyInput


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
    ) -> None:
        self.runtime = runtime or PaperTradingRuntime()
        self.strategy_engine = StrategyEngine(self._coerce_strategy_config(strategy_config))
        self.risk_enabled = risk_enabled

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
        for _, row in working.iterrows():
            price = float(row[price_column])
            strategy_input = self._strategy_input_from_row(row)
            strategy, _trace = self.strategy_engine.decide(strategy_input)
            risk = evaluate_strategy_risk(
                strategy,
                risk_enabled=self.risk_enabled,
            )
            authorization = authorize_risk_decision(risk)

            order = None
            if authorization.status.value == "AUTHORIZED":
                order = self.runtime.submit(
                    authorization,
                    price=price,
                    quantity=quantity,
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
