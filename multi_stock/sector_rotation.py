"""Point-in-time descriptive sector rotation for Module 6 M02."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd


@dataclass(frozen=True, slots=True)
class SectorRotationRow:
    """One sector's observed return state at a decision timestamp."""

    sector_index_symbol: str
    return_1: float | None
    return_3: float | None
    return_12: float | None

    def __post_init__(self) -> None:
        symbol = self.sector_index_symbol.strip().upper()
        if not symbol:
            raise ValueError("sector_index_symbol must not be empty")
        object.__setattr__(self, "sector_index_symbol", symbol)
        for name in ("return_1", "return_3", "return_12"):
            value = getattr(self, name)
            if value is not None and not pd.notna(float(value)):
                raise ValueError(f"{name} must be finite or None")
            if value is not None:
                object.__setattr__(self, name, float(value))


@dataclass(frozen=True, slots=True)
class SectorRotation:
    """Immutable sector-return snapshot; descriptive only."""

    timestamp: pd.Timestamp
    rows: tuple[SectorRotationRow, ...]
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        symbols = tuple(row.sector_index_symbol for row in self.rows)
        if len(symbols) != len(set(symbols)):
            raise ValueError("sector rows must be unique")
        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(
            self,
            "rows",
            tuple(sorted(self.rows, key=lambda row: row.sector_index_symbol)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "rows": [
                {
                    "sector_index_symbol": row.sector_index_symbol,
                    "return_1": row.return_1,
                    "return_3": row.return_3,
                    "return_12": row.return_12,
                }
                for row in self.rows
            ],
            "authority": self.authority,
        }


def build_sector_rotation(
    *,
    timestamp: Any,
    sector_context: Iterable[dict[str, Any]] | pd.DataFrame,
) -> SectorRotation:
    """Build a causal sector-rotation snapshot from already-derived context.

    The function only consumes rows whose timestamp is at or before the
    requested timestamp. It does not infer sector membership or create
    trading signals.
    """
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    frame = (
        sector_context.copy()
        if isinstance(sector_context, pd.DataFrame)
        else pd.DataFrame(tuple(sector_context))
    )
    required = {
        "timestamp",
        "sector_index_symbol",
        "return_1",
        "return_3",
        "return_12",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"sector_context missing columns: {sorted(missing)}")
    if frame.empty:
        return SectorRotation(timestamp=ts, rows=())

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["sector_index_symbol"] = (
        frame["sector_index_symbol"].astype("string").str.strip().str.upper()
    )
    if frame["sector_index_symbol"].isna().any() or (
        frame["sector_index_symbol"] == ""
    ).any():
        raise ValueError("sector_index_symbol must be non-empty")

    frame = frame.loc[frame["timestamp"] <= ts].copy()
    if frame.empty:
        return SectorRotation(timestamp=ts, rows=())

    frame = frame.sort_values(
        ["sector_index_symbol", "timestamp"], kind="stable"
    )
    latest = frame.groupby("sector_index_symbol", sort=True, as_index=False).tail(1)

    rows = tuple(
        SectorRotationRow(
            sector_index_symbol=str(row.sector_index_symbol),
            return_1=None if pd.isna(row.return_1) else float(row.return_1),
            return_3=None if pd.isna(row.return_3) else float(row.return_3),
            return_12=None if pd.isna(row.return_12) else float(row.return_12),
        )
        for row in latest.sort_values("sector_index_symbol", kind="stable").itertuples()
    )
    return SectorRotation(timestamp=ts, rows=rows)
