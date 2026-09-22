"""MB-16 validation and leakage guards."""
import pandas as pd
def validate_market_input(data):
    if not isinstance(data,pd.DataFrame): raise TypeError("data must be a pandas DataFrame")
    missing={"timestamp","close"}-set(data.columns)
    if missing: raise ValueError(f"missing required columns: {sorted(missing)}")
    ts=pd.to_datetime(data.timestamp,utc=True)
    if "symbol" in data and data.duplicated(["timestamp","symbol"]).any(): raise ValueError("duplicate timestamp/symbol observations")
    if "symbol" not in data and ts.duplicated().any(): raise ValueError("duplicate timestamps")
def validate_state(state):
    if state.timestamp.tzinfo is None: raise ValueError("state timestamp must be timezone-aware")
    if state.regime_probability is not None and not 0<=state.regime_probability<=1: raise ValueError("invalid regime_probability")
    if state.quality is not None and not 0<=state.quality<=1: raise ValueError("invalid quality")
def assert_no_future_rows(history,extended,timestamp_column="timestamp"):
    cutoff=pd.to_datetime(history[timestamp_column],utc=True).max()
    if len(extended.loc[pd.to_datetime(extended[timestamp_column],utc=True)<=cutoff])<len(history): raise AssertionError("extended data lost historical rows")
