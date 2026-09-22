"""MB-10 causal market strength/weakness engine."""
from __future__ import annotations
import numpy as np
import pandas as pd

class MarketStrengthEngine:
    def __init__(self,baseline_window:int=60)->None:
        if baseline_window<5: raise ValueError("baseline_window must be >= 5")
        self.baseline_window=baseline_window

    def calculate(self,benchmark:pd.DataFrame,breadth:pd.DataFrame|None=None)->pd.DataFrame:
        required={"timestamp","close"}
        missing=required.difference(benchmark.columns)
        if missing: raise ValueError(f"benchmark missing: {sorted(missing)}")
        frame=benchmark.loc[:,["timestamp","close"]].copy()
        frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
        frame["close"]=pd.to_numeric(frame["close"],errors="coerce")
        frame=frame.sort_values("timestamp")
        ret=frame["close"].pct_change()
        baseline=ret.rolling(self.baseline_window,min_periods=self.baseline_window).median().shift(1)
        dispersion=ret.rolling(self.baseline_window,min_periods=self.baseline_window).std().shift(1)
        z=(ret-baseline).div(dispersion.replace(0,np.nan))
        price_score=(0.5+0.5*np.tanh(z/2.0)).where(z.notna())
        score=price_score
        if breadth is not None and {"timestamp","positive_pct"}.issubset(breadth.columns):
            b=breadth[["timestamp","positive_pct"]].copy()
            b["timestamp"]=pd.to_datetime(b["timestamp"],utc=True)
            frame=frame.merge(b,on="timestamp",how="left",validate="one_to_one")
            score=(0.7*price_score+0.3*frame["positive_pct"]).where(price_score.notna() & frame["positive_pct"].notna())
        frame["strength_score"]=score.clip(0.0,1.0)
        frame["strength_state"]=np.select(
            [frame["strength_score"].isna(),frame["strength_score"]>=0.60,frame["strength_score"]<=0.40],
            ["UNAVAILABLE","STRONG","WEAK"],default="NEUTRAL")
        return frame[["timestamp","strength_score","strength_state"]]
