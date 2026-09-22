"""Sector intelligence over PIT-mapped constituents."""
from __future__ import annotations
import numpy as np
import pandas as pd

class SectorEngine:
    def calculate(self, data: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
        required={"timestamp","symbol","close"}
        missing=required.difference(data.columns)
        if missing: raise ValueError(f"data missing: {sorted(missing)}")
        mreq={"timestamp","symbol","sector"}
        missing=mreq.difference(membership.columns)
        if missing: raise ValueError(f"membership missing: {sorted(missing)}")
        prices=data.loc[:,["timestamp","symbol","close"]].copy()
        prices["timestamp"]=pd.to_datetime(prices["timestamp"],utc=True)
        prices["symbol"]=prices["symbol"].astype(str).str.upper().str.strip()
        prices["close"]=pd.to_numeric(prices["close"],errors="coerce")
        prices=prices.sort_values(["symbol","timestamp"],kind="stable")
        prices["return_1"]=prices.groupby("symbol",sort=False)["close"].pct_change()
        sectors=membership.loc[:,["timestamp","symbol","sector"]].copy()
        sectors["timestamp"]=pd.to_datetime(sectors["timestamp"],utc=True)
        sectors["symbol"]=sectors["symbol"].astype(str).str.upper().str.strip()
        sectors["sector"]=sectors["sector"].astype(str).str.strip().str.upper()
        merged=prices.merge(sectors,on=["timestamp","symbol"],how="left",validate="many_to_one").dropna(subset=["sector"])
        return (merged.groupby(["timestamp","sector"],sort=True)
                .agg(constituent_count=("symbol","nunique"),
                     sector_return=("return_1","mean"),
                     sector_positive_pct=("return_1",lambda x: float((x>0).mean()) if x.notna().any() else np.nan))
                .reset_index())

def rank_sector_strength(sector_frame: pd.DataFrame) -> pd.DataFrame:
    required={"timestamp","sector","sector_return"}
    missing=required.difference(sector_frame.columns)
    if missing: raise ValueError(f"missing: {sorted(missing)}")
    result=sector_frame.copy()
    result["sector_rank"]=result.groupby("timestamp")["sector_return"].rank(method="average",ascending=False)
    counts=result.groupby("timestamp")["sector"].transform("count")
    result["sector_strength_pct"]=1.0-(result["sector_rank"]-1.0)/counts.replace(0,np.nan)
    return result
