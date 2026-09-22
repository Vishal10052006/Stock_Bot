"""Cross-module Market Bot validation."""
from __future__ import annotations

import numpy as np
import pandas as pd


def validate_market_inputs(
    benchmark: pd.DataFrame,
    constituents: pd.DataFrame | None = None,
) -> None:
    """Validate the shared causal boundary before component engines run."""
    if not isinstance(benchmark, pd.DataFrame):
        raise TypeError("benchmark must be a pandas DataFrame")
    required_benchmark = {"timestamp", "close"}
    missing = required_benchmark.difference(benchmark.columns)
    if missing:
        raise ValueError(f"benchmark missing: {sorted(missing)}")
    if benchmark.empty:
        raise ValueError("benchmark must not be empty")

    ts = pd.to_datetime(benchmark["timestamp"], utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError("benchmark timestamp contains invalid values")
    if not ts.is_monotonic_increasing:
        raise ValueError("benchmark timestamps must be ordered")
    if ts.duplicated().any():
        raise ValueError("benchmark timestamps must be unique")

    close = pd.to_numeric(benchmark["close"], errors="coerce")
    if not np.isfinite(close).all() or (close <= 0).any():
        raise ValueError("benchmark close must be finite and positive")

    if constituents is None:
        return

    if not isinstance(constituents, pd.DataFrame):
        raise TypeError("constituents must be a pandas DataFrame")

    required = {"timestamp", "symbol", "close"}
    missing = required.difference(constituents.columns)
    if missing:
        raise ValueError(f"constituents missing: {sorted(missing)}")
    if constituents.empty:
        raise ValueError("constituents must not be empty")

    cts = pd.to_datetime(
        constituents["timestamp"], utc=True, errors="coerce"
    )
    if cts.isna().any():
        raise ValueError("constituent timestamp contains invalid values")
    if cts.max() > ts.max():
        raise ValueError("constituent data extends beyond benchmark cutoff")

    symbols = constituents["symbol"].astype(str).str.strip().str.upper()
    if symbols.eq("").any():
        raise ValueError("constituent symbol must not be empty")

    duplicate_keys = constituents.assign(
        _timestamp=cts,
        _symbol=symbols,
    ).duplicated(["_timestamp", "_symbol"])
    if duplicate_keys.any():
        raise ValueError("duplicate timestamp/symbol constituent observations")

    cclose = pd.to_numeric(constituents["close"], errors="coerce")
    if not np.isfinite(cclose).all() or (cclose <= 0).any():
        raise ValueError("constituent close must be finite and positive")
