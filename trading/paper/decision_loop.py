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
from trading.strategy.baseline import evaluate_row
from trading.strategy.models import BaselineStrategyConfig, StrategyDecision


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
        strategy_config: BaselineStrategyConfig | None = None,
        risk_enabled: bool = True,
    ) -> None:
        self.runtime = runtime or PaperTradingRuntime()
        self.strategy_config = strategy_config or BaselineStrategyConfig()
        self.risk_enabled = risk_enabled

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
            strategy = evaluate_row(row, config=self.strategy_config)
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
