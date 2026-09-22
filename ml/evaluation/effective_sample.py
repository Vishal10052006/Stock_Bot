"""Effective-sample-size diagnostics for Phase 9.

This is a diagnostic, not a claim of independent observations. The report
makes overlapping labels and clustering explicit so downstream statistical
interpretation cannot silently treat every row as independent.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class EffectiveSampleDiagnostics:
    """Auditable dependence diagnostics."""

    observations: int
    unique_symbols: int
    unique_dates: int
    unique_timestamps: int
    observations_per_symbol_max: int
    observations_per_date_max: int
    overlap_warning: bool


def diagnose_effective_sample(
    data: pd.DataFrame,
    *,
    label_horizon_minutes: int,
) -> EffectiveSampleDiagnostics:
    """Report clustering/overlap diagnostics without inventing an ESS formula."""
    if label_horizon_minutes <= 0:
        raise ValueError("label_horizon_minutes must be greater than zero")
    required = {"timestamp", "symbol"}
    if not required.issubset(data.columns):
        raise ValueError("data must contain timestamp and symbol")

    timestamps = pd.to_datetime(data["timestamp"], utc=True)
    symbols = data["symbol"].astype(str)
    dates = timestamps.dt.date

    overlap_warning = bool(
        timestamps.sort_values().diff().dropna().dt.total_seconds().le(
            label_horizon_minutes * 60
        ).any()
    )

    return EffectiveSampleDiagnostics(
        observations=len(data),
        unique_symbols=int(symbols.nunique()),
        unique_dates=int(dates.nunique()),
        unique_timestamps=int(timestamps.nunique()),
        observations_per_symbol_max=int(symbols.value_counts().max()),
        observations_per_date_max=int(dates.value_counts().max()),
        overlap_warning=overlap_warning,
    )
