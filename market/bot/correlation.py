"""Rolling correlation and dependency-state engine."""
from __future__ import annotations
import numpy as np
import pandas as pd

class CorrelationEngine:
    def __init__(self, window:int=60, min_periods:int=30, high_threshold:float=0.70) -> None:
        if window<3 or min_periods<2 or min_periods>window: raise ValueError("invalid correlation parameters")
        self.window=window; self.min_periods=min_periods; self.high_threshold=high_threshold

    def calculate(self, data:pd.DataFrame, benchmark:str)->pd.DataFrame:
        required={"timestamp","symbol","close"}
        missing=required.difference(data.columns)
        if missing: raise ValueError(f"missing: {sorted(missing)}")
        frame=data.loc[:,["timestamp","symbol","close"]].copy()
        frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
        frame["symbol"]=frame["symbol"].astype(str).str.upper().str.strip()
        frame["close"]=pd.to_numeric(frame["close"],errors="coerce")
        frame=frame.sort_values(["symbol","timestamp"],kind="stable")
        frame["ret"]=frame.groupby("symbol",sort=False)["close"].pct_change()
        pivot=frame.pivot(index="timestamp",columns="symbol",values="ret").sort_index()
        benchmark=benchmark.strip().upper()
        if benchmark not in pivot.columns: raise ValueError(f"benchmark {benchmark} not present in data")
        rows=[]
        for ts in pivot.index:
            history=pivot.loc[:ts].tail(self.window)
            if len(history)<self.min_periods:
                rows.append((ts,np.nan,"UNAVAILABLE",0)); continue
            corrs=history.drop(columns=[benchmark]).corrwith(history[benchmark],min_periods=self.min_periods).dropna()
            if corrs.empty:
                rows.append((ts,np.nan,"UNAVAILABLE",0)); continue
            mean_abs=float(corrs.abs().mean())
            rows.append((ts,mean_abs,"HIGH" if mean_abs>=self.high_threshold else "NORMAL",int(corrs.notna().sum())))
        return pd.DataFrame(rows,columns=["timestamp","mean_abs_market_correlation","correlation_state","observations"])

def correlation_matrix(data:pd.DataFrame,timestamp:pd.Timestamp,window:int=60)->pd.DataFrame:
    frame=data.copy()
    frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
    frame=frame.loc[frame["timestamp"]<=timestamp].sort_values(["symbol","timestamp"],kind="stable")
    frame["ret"]=frame.groupby("symbol",sort=False)["close"].pct_change()
    pivot=frame.pivot(index="timestamp",columns="symbol",values="ret").tail(window)
    return pivot.corr()
