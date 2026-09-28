"""Robustness evaluation across market regimes, symbols, and dates.

The helpers consume frozen out-of-sample predictions only.  They never fit,
select, or tune a model and therefore cannot leak future labels into training.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .stratified import StratifiedEvaluation, evaluate_by_column


@dataclass(frozen=True, slots=True)
class RobustnessReport:
    """Deterministic stratified evaluation bundle."""

    by_regime: tuple[StratifiedEvaluation, ...] = ()
    by_symbol: tuple[StratifiedEvaluation, ...] = ()
    by_date: tuple[StratifiedEvaluation, ...] = ()


def evaluate_robustness(
    y_true: pd.Series,
    probabilities: pd.DataFrame,
    metadata: pd.DataFrame,
    *,
    regime_column: str | None = "regime",
    symbol_column: str = "symbol",
    timestamp_column: str = "timestamp",
) -> RobustnessReport:
    """Evaluate existing OOS predictions across deterministic slices."""
    if timestamp_column not in metadata.columns:
        raise ValueError(f"metadata is missing required column: {timestamp_column}")
    if symbol_column not in metadata.columns:
        raise ValueError(f"metadata is missing required column: {symbol_column}")

    by_regime = (
        evaluate_by_column(
            y_true,
            probabilities,
            metadata,
            column=regime_column,
        )
        if regime_column is not None and regime_column in metadata.columns
        else ()
    )

    by_symbol = evaluate_by_column(
        y_true,
        probabilities,
        metadata,
        column=symbol_column,
    )

    dated = metadata.copy()
    dated["_decision_date"] = pd.to_datetime(
        dated[timestamp_column],
        utc=True,
        errors="raise",
    ).dt.strftime("%Y-%m-%d")
    by_date = evaluate_by_column(
        y_true,
        probabilities,
        dated,
        column="_decision_date",
    )

    return RobustnessReport(
        by_regime=tuple(by_regime),
        by_symbol=tuple(by_symbol),
        by_date=tuple(by_date),
    )
