"""
Validation helpers for Phase 8 baseline strategy outputs.
"""

from __future__ import annotations

import pandas as pd

from .models import StrategyDirection


REQUIRED_OUTPUT_COLUMNS = (
    "timestamp",
    "symbol",
    "direction",
    "strategy_version",
    "rationale",
)


def validate_strategy_output(data: pd.DataFrame) -> None:
    """
    Validate the deterministic strategy output contract.
    """

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

    observed = set(data["direction"].dropna().astype(str))

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