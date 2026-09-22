"""Validation helpers for Strategy Engine outputs."""

from __future__ import annotations

import math

import pandas as pd

from .models import (
    NoTradeReason,
    StrategyDecision,
    StrategyDirection,
)


REQUIRED_OUTPUT_COLUMNS = (
    "timestamp",
    "symbol",
    "direction",
    "strategy_version",
    "rationale",
)


def validate_strategy_decision(
    decision: StrategyDecision,
) -> None:
    """Validate one StrategyDecision contract."""
    if not isinstance(decision, StrategyDecision):
        raise TypeError("decision must be a StrategyDecision")

    if pd.Timestamp(decision.timestamp).tzinfo is None:
        raise ValueError("strategy timestamp must be timezone-aware")

    if not decision.symbol.strip():
        raise ValueError("strategy symbol must not be empty")

    if not decision.strategy_version.strip():
        raise ValueError("strategy_version must not be empty")

    if not isinstance(decision.direction, StrategyDirection):
        raise ValueError("invalid strategy direction")

    if (
        decision.direction is StrategyDirection.NO_TRADE
        and decision.primary_reason is None
    ):
        raise ValueError("NO_TRADE requires primary_reason")

    if (
        decision.direction is not StrategyDirection.NO_TRADE
        and decision.primary_reason is not None
    ):
        raise ValueError("TRADE cannot have primary_reason")

    if decision.primary_reason is not None and not isinstance(
        decision.primary_reason,
        NoTradeReason,
    ):
        raise ValueError("invalid primary NoTradeReason")

    for name, value in (
        ("prediction_probability", decision.prediction_probability),
        ("regime_probability", decision.regime_probability),
    ):
        if value is not None and not 0.0 <= float(value) <= 1.0:
            raise ValueError(
                f"{name} must be in [0, 1]"
            )

    for name, value in (
        ("entry_reference", decision.entry_reference),
        ("stop_reference", decision.stop_reference),
        ("target_reference", decision.target_reference),
        ("expected_reward", decision.expected_reward),
        ("expected_loss", decision.expected_loss),
        ("expected_value", decision.expected_value),
        ("estimated_cost", decision.estimated_cost),
        ("slippage_assumption_bps", decision.slippage_assumption_bps),
    ):
        if value is not None and not math.isfinite(float(value)):
            raise ValueError(
                f"{name} must be finite"
            )

    if decision.direction is StrategyDirection.NO_TRADE:
        return

    if decision.direction in {
        StrategyDirection.LONG,
        StrategyDirection.SHORT,
    } and decision.symbol.strip() == "":
        raise ValueError("trade symbol must not be empty")


def validate_strategy_output(
    data: pd.DataFrame,
) -> None:
    """Validate the legacy deterministic tabular output contract."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("strategy output must be a pandas DataFrame")

    missing = set(REQUIRED_OUTPUT_COLUMNS).difference(data.columns)
    if missing:
        raise ValueError(
            f"strategy output is missing columns: {sorted(missing)}"
        )

    allowed = {
        direction.value
        for direction in StrategyDirection
    }

    observed = set(
        data["direction"].dropna().astype(str)
    )

    unexpected = observed.difference(allowed)

    if unexpected:
        raise ValueError(
            f"unexpected strategy directions: {sorted(unexpected)}"
        )

    if data["timestamp"].isna().any():
        raise ValueError(
            "strategy timestamps must not be missing"
        )

    if data["symbol"].astype(str).str.strip().eq("").any():
        raise ValueError(
            "strategy symbols must not be empty"
        )
