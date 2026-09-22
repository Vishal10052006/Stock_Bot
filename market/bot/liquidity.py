"""Market-level liquidity and participation engine."""
from __future__ import annotations
import numpy as np
import pandas as pd

class LiquidityEngine:
    def __init__(self,window:int=20,high_ratio:float=1.25,low_ratio:float=0.75)->None:
        if window<2 or not 0<low_ratio<1<high_ratio: raise ValueError("invalid liquidity parameters")
        self.window=window; self.high_ratio=high_ratio; self.low_ratio=low_ratio

    def calculate(self,data:pd.DataFrame)->pd.DataFrame:
        required={"timestamp","symbol","close","volume"}
        missing=required.difference(data.columns)
        if missing: raise ValueError(f"missing: {sorted(missing)}")
        frame=data.loc[:,["timestamp","symbol","close","volume"]].copy()
        frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
        frame["symbol"]=frame["symbol"].astype(str).str.upper().str.strip()
        frame["close"]=pd.to_numeric(frame["close"],errors="coerce")
        frame["volume"]=pd.to_numeric(frame["volume"],errors="coerce")
        frame["turnover"]=frame["close"]*frame["volume"]
        daily=frame.groupby("timestamp",sort=True).agg(market_turnover=("turnover","sum"),active_symbols=("symbol","nunique"))
        daily["turnover_baseline"]=daily["market_turnover"].rolling(self.window,min_periods=self.window).median().shift(1)
        daily["turnover_ratio"]=daily["market_turnover"].div(daily["turnover_baseline"].replace(0,np.nan))
        daily["liquidity_state"]="UNAVAILABLE"
        daily.loc[daily["turnover_ratio"]>=self.high_ratio,"liquidity_state"]="HIGH"
        daily.loc[(daily["turnover_ratio"]>self.low_ratio)&(daily["turnover_ratio"]<self.high_ratio),"liquidity_state"]="NORMAL"
        daily.loc[daily["turnover_ratio"]<=self.low_ratio,"liquidity_state"]="LOW"
        return daily.reset_index()
