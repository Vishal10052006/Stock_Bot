"""Point-in-time cross-stock correlation for Module 6 M04."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class CorrelationMatrix:
    """Immutable descriptive pairwise correlation snapshot."""

    timestamp: pd.Timestamp
    symbols: tuple[str, ...]
    matrix: tuple[tuple[float | None, ...], ...]
    observations: int
    return_key: str
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if len(self.matrix) != len(self.symbols):
            raise ValueError("matrix dimension must match symbols")
        if any(len(row) != len(self.symbols) for row in self.matrix):
            raise ValueError("matrix must be square")
        if any(
            value is not None and not -1.0 <= float(value) <= 1.0
            for row in self.matrix
            for value in row
        ):
            raise ValueError("correlations must be in [-1, 1]")
        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(
            self,
            "symbols",
            tuple(symbol.strip().upper() for symbol in self.symbols),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbols": list(self.symbols),
            "matrix": [list(row) for row in self.matrix],
            "observations": self.observations,
            "return_key": self.return_key,
            "authority": self.authority,
        }


def build_correlation_matrix(
    *,
    timestamp: Any,
    returns: pd.DataFrame,
    universe_symbols: tuple[str, ...] | list[str],
    return_key: str = "return_1",
    min_observations: int = 2,
) -> CorrelationMatrix:
    """Compute a causal pairwise correlation matrix from historical returns.

    Only rows with timestamp <= the requested timestamp are eligible. Missing
    values are handled pairwise by pandas; no future values or imputation are
    introduced. A pair with insufficient overlapping observations is None.
    """
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    if min_observations < 2:
        raise ValueError("min_observations must be >= 2")
    if not isinstance(returns, pd.DataFrame):
        raise TypeError("returns must be a pandas DataFrame")

    symbols = tuple(sorted({str(s).strip().upper() for s in universe_symbols}))
    if any(not s for s in symbols):
        raise ValueError("universe_symbols must contain non-empty symbols")
    required = {"timestamp", "symbol", return_key}
    missing = required.difference(returns.columns)
    if missing:
        raise ValueError(f"returns missing columns: {sorted(missing)}")

    frame = returns.loc[:, ["timestamp", "symbol", return_key]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["symbol"] = frame["symbol"].astype("string").str.strip().str.upper()
    frame = frame.loc[
        frame["timestamp"] <= ts,
        ["timestamp", "symbol", return_key],
    ].copy()
    frame = frame[frame["symbol"].isin(symbols)]
    if frame.empty:
        return CorrelationMatrix(
            timestamp=ts, symbols=symbols,
            matrix=tuple(tuple(None for _ in symbols) for _ in symbols),
            observations=0, return_key=return_key,
        )

    if frame.duplicated(["timestamp", "symbol"]).any():
        raise ValueError("returns contains duplicate symbol/timestamp rows")
    frame[return_key] = pd.to_numeric(frame[return_key], errors="coerce")
    pivot = frame.pivot(index="timestamp", columns="symbol", values=return_key)
    pivot = pivot.reindex(columns=symbols)
    correlation = pivot.corr(method="pearson", min_periods=min_observations)

    overlap = pivot.notna().astype(int).T.dot(pivot.notna().astype(int))
    matrix: list[tuple[float | None, ...]] = []
    for left in symbols:
        row: list[float | None] = []
        for right in symbols:
            if overlap.loc[left, right] < min_observations:
                row.append(None)
            elif left == right:
                row.append(1.0)
            else:
                value = correlation.loc[left, right]
                row.append(None if pd.isna(value) else float(value))
        matrix.append(tuple(row))

    return CorrelationMatrix(
        timestamp=ts,
        symbols=symbols,
        matrix=tuple(matrix),
        observations=len(pivot),
        return_key=return_key,
    )
