"""Validation and audit helpers for historical fundamental datasets."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from intelligence.analysis.fundamentals.contracts import FundamentalSnapshot


@dataclass(frozen=True, slots=True)
class FundamentalValidationReport:
    observations: int
    symbols: int
    duplicate_keys: int
    invalid_causal_rows: int
    finite_rows: int
    valid: bool


def validate_fundamental_snapshots(
    snapshots: Iterable[FundamentalSnapshot],
) -> FundamentalValidationReport:
    """Validate normalized snapshots without using future outcomes."""
    rows = tuple(snapshots)
    keys = [
        (
            row.symbol,
            row.period_start,
            row.period_end,
            row.available_at,
            row.source,
        )
        for row in rows
    ]
    duplicate_keys = len(keys) - len(set(keys))
    invalid_causal_rows = sum(
        row.published_at > row.available_at or row.period_start > row.period_end
        for row in rows
    )
    # Construction of FundamentalSnapshot already rejects non-finite metrics.
    finite_rows = sum(1 for row in rows if all(map(_finite, row.metrics.values())))
    symbols = len({row.symbol for row in rows})
    valid = bool(rows) and duplicate_keys == 0 and invalid_causal_rows == 0 and finite_rows == len(rows)
    return FundamentalValidationReport(
        observations=len(rows),
        symbols=symbols,
        duplicate_keys=duplicate_keys,
        invalid_causal_rows=invalid_causal_rows,
        finite_rows=finite_rows,
        valid=valid,
    )


def _finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))
