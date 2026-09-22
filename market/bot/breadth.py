"""MB-05 constituent breadth engine."""
from __future__ import annotations
import numpy as np
import pandas as pd

class BreadthEngine:
    def __init__(self, return_window:int=1)->None:
        if return_window<1: raise ValueError("return_window must be >= 1")
        self.return_window=return_window

    def calculate(self,data:pd.DataFrame)->pd.DataFrame:
        required={"timestamp","symbol","close"}
        missing=required.difference(data.columns)
        if missing: raise ValueError(f"missing required columns: {sorted(missing)}")
        frame=data.loc[:,["timestamp","symbol","close"]].copy()
        frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
        frame["symbol"]=frame["symbol"].astype(str).str.strip().str.upper()
        frame["close"]=pd.to_numeric(frame["close"],errors="coerce")
        if frame.duplicated(["timestamp","symbol"]).any(): raise ValueError("duplicate timestamp/symbol observations")
        frame=frame.sort_values(["symbol","timestamp"],kind="stable")
        frame["constituent_return"]=frame.groupby("symbol",sort=False)["close"].pct_change(self.return_window)
        frame["advancing"]=frame["constituent_return"]>0
        frame["declining"]=frame["constituent_return"]<0
        frame["unchanged"]=frame["constituent_return"].eq(0)
        result=(frame.groupby("timestamp",sort=True)
                .agg(constituents=("symbol","nunique"),advancing=("advancing","sum"),
                     declining=("declining","sum"),unchanged=("unchanged","sum"))
                .reset_index())
        active=result["advancing"]+result["declining"]+result["unchanged"]
        result["advance_decline_ratio"]=result["advancing"].div(result["declining"].replace(0,np.nan))
        result["positive_pct"]=result["advancing"].div(active.replace(0,np.nan))
        result["breadth_state"]=np.select(
            [active.eq(0),result["positive_pct"]>=0.60,result["positive_pct"]<=0.40],
            ["UNAVAILABLE","POSITIVE","NEGATIVE"],default="MIXED")
        return result
