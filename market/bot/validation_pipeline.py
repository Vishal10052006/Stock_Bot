"""Cross-module Market Bot validation."""
from __future__ import annotations
import pandas as pd

def validate_market_inputs(benchmark:pd.DataFrame,constituents:pd.DataFrame|None=None)->None:
    if benchmark.empty: raise ValueError("benchmark must not be empty")
    ts=pd.to_datetime(benchmark["timestamp"],utc=True)
    if not ts.is_monotonic_increasing: raise ValueError("benchmark timestamps must be ordered")
    if ts.duplicated().any(): raise ValueError("benchmark timestamps must be unique")
    if constituents is not None:
        required={"timestamp","symbol","close"}
        missing=required.difference(constituents.columns)
        if missing: raise ValueError(f"constituents missing: {sorted(missing)}")
        cts=pd.to_datetime(constituents["timestamp"],utc=True)
        if cts.max()>ts.max(): raise ValueError("constituent data extends beyond benchmark cutoff")
