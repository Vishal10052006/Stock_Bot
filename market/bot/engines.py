"""MB-02..MB-10 deterministic causal market intelligence engines."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
def _frame(data):
    if not isinstance(data,pd.DataFrame): raise TypeError("data must be a pandas DataFrame")
    if "timestamp" not in data: raise ValueError("timestamp is required")
    x=data.copy(); x["timestamp"]=pd.to_datetime(x["timestamp"],utc=True)
    if x["timestamp"].duplicated().any() and "symbol" not in x: raise ValueError("duplicate timestamps require symbol")
    return x.sort_values(["timestamp","symbol"] if "symbol" in x else ["timestamp"],kind="stable")
@dataclass(frozen=True,slots=True)
class MarketTrendEngine:
    fast_window:int=20; slow_window:int=50; slope_window:int=20
    def calculate(self,data):
        f=_frame(data); c=pd.to_numeric(f["close"],errors="coerce"); fast=c.rolling(self.fast_window,min_periods=self.fast_window).mean(); slow=c.rolling(self.slow_window,min_periods=self.slow_window).mean(); spread=fast/slow-1; slope=slow.pct_change(self.slope_window); score=(np.sign(spread.fillna(0))+np.sign(slope.fillna(0))+np.sign((c/slow-1).fillna(0)))/3
        f["trend_fast_ma"]=fast; f["trend_slow_ma"]=slow; f["trend_slope"]=slope; f["trend_strength"]=score.abs().clip(0,1); f["trend_state"]="UNAVAILABLE"; ready=fast.notna()&slow.notna()&slope.notna(); f.loc[ready&(score>=.667),"trend_state"]="UP"; f.loc[ready&(score<=-.667),"trend_state"]="DOWN"; f.loc[ready&(score.abs()<.667),"trend_state"]="MIXED"; return f
@dataclass(frozen=True,slots=True)
class MarketRangeEngine:
    window:int=20
    def calculate(self,data):
        f=_frame(data); h=pd.to_numeric(f["high"],errors="coerce"); l=pd.to_numeric(f["low"],errors="coerce"); c=pd.to_numeric(f["close"],errors="coerce"); width=(h.rolling(self.window).max()-l.rolling(self.window).min())/c; path=c.diff().abs().rolling(self.window).sum(); eff=c.diff(self.window).abs()/path.replace(0,np.nan); f["range_width"]=width; f["range_efficiency"]=eff; f["range_state"]="UNAVAILABLE"; ready=width.notna()&eff.notna(); f.loc[ready&(eff<.25),"range_state"]="RANGE"; f.loc[ready&(eff>=.25),"range_state"]="TREND"; return f
@dataclass(frozen=True,slots=True)
class MarketVolatilityEngine:
    window:int=20
    def calculate(self,data):
        f=_frame(data); c=pd.to_numeric(f["close"],errors="coerce"); r=c.pct_change(); rv=r.rolling(self.window).std()*np.sqrt(252); p=c.shift(1); h=pd.to_numeric(f["high"],errors="coerce"); l=pd.to_numeric(f["low"],errors="coerce"); tr=pd.concat([h-l,(h-p).abs(),(l-p).abs()],axis=1).max(axis=1); f["volatility_realized"]=rv; f["volatility_atr_normalized"]=tr.rolling(self.window).mean()/c; base=rv.rolling(self.window,min_periods=self.window).median().shift(1); f["volatility_state"]="UNAVAILABLE"; ready=rv.notna(); f.loc[ready&base.notna()&(rv>base*1.5),"volatility_state"]="HIGH"; f.loc[ready&base.notna()&(rv<base*.67),"volatility_state"]="LOW"; f.loc[ready&f["volatility_state"].eq("UNAVAILABLE"),"volatility_state"]="NORMAL"; return f
class MarketBreadthEngine:
    def calculate(self,data):
        f=_frame(data)
        if "symbol" not in f: raise ValueError("symbol is required for breadth")
        f["_r"]=pd.to_numeric(f["close"],errors="coerce").groupby(f["symbol"]).pct_change(); rows=[]
        for ts,g in f.groupby("timestamp",sort=True):
            r=g["_r"].dropna(); p=np.nan if r.empty else float((r>0).mean()); rows.append({"timestamp":ts,"breadth_positive_pct":p,"breadth_state":"UNAVAILABLE" if r.empty else ("POSITIVE" if p>=.60 else ("NEGATIVE" if p<=.40 else "NEUTRAL"))})
        return pd.DataFrame(rows)
class SectorIntelligenceEngine:
    def calculate(self,data):
        f=_frame(data)
        if "sector" not in f: return pd.DataFrame(columns=["timestamp","sector","sector_return_1","sector_state"])
        f["_r"]=pd.to_numeric(f["close"],errors="coerce").groupby(f["symbol"]).pct_change() if "symbol" in f else pd.to_numeric(f["close"],errors="coerce").pct_change(); o=f.groupby(["timestamp","sector"],sort=True)["_r"].mean().rename("sector_return_1").reset_index(); o["sector_state"]=np.where(o.sector_return_1>0,"STRONG",np.where(o.sector_return_1<0,"WEAK","NEUTRAL")); return o
class SectorRotationEngine:
    def calculate(self,sector_data):
        if sector_data.empty: return sector_data.assign(rotation_state=pd.Series(dtype=str))
        x=sector_data.copy(); x["rotation_state"]="NEUTRAL"
        for _,g in x.groupby("timestamp",sort=True):
            r=g.sector_return_1.rank(pct=True); x.loc[g.index[r>=.75],"rotation_state"]="LEADING"; x.loc[g.index[r<=.25],"rotation_state"]="LAGGING"
        return x
class CorrelationDependencyEngine:
    def __init__(self,window=20): self.window=window
    def calculate(self,data):
        f=_frame(data)
        if "symbol" not in f: return pd.DataFrame(columns=["timestamp","correlation_mean","correlation_state"])
        ret=f.pivot(index="timestamp",columns="symbol",values="close").pct_change(); rows=[]
        for ts,g in ret.rolling(self.window).corr().groupby(level=0):
            a=g.to_numpy(); a=a[np.triu_indices_from(a,k=1)]; a=a[np.isfinite(a)]; rows.append({"timestamp":ts,"correlation_mean":float(a.mean()) if a.size else np.nan})
        o=pd.DataFrame(rows); o["correlation_state"]=np.where(o.correlation_mean>=.70,"HIGH",np.where(o.correlation_mean<=.30,"LOW","MEDIUM")); o.loc[o.correlation_mean.isna(),"correlation_state"]="UNAVAILABLE"; return o
class LiquidityFlowEngine:
    def __init__(self,window=20): self.window=window
    def calculate(self,data):
        f=_frame(data); c=pd.to_numeric(f.close,errors="coerce"); v=pd.to_numeric(f.volume,errors="coerce"); f["liquidity_value"]=c*v; f["liquidity_baseline"]=f.groupby("symbol").liquidity_value.transform(lambda s:s.rolling(self.window).median().shift(1)) if "symbol" in f else f.liquidity_value.rolling(self.window).median().shift(1); ratio=f.liquidity_value/f.liquidity_baseline; f["liquidity_state"]="UNAVAILABLE"; f.loc[ratio>=1.2,"liquidity_state"]="IMPROVING"; f.loc[ratio<=.8,"liquidity_state"]="WEAKENING"; f.loc[ratio.between(.8,1.2),"liquidity_state"]="STABLE"; return f
class MarketStrengthEngine:
    def calculate(self,data):
        f=_frame(data); comps=[]
        if "trend_strength" in f: comps.append(pd.to_numeric(f.trend_strength,errors="coerce"))
        if "close" in f: comps.append(pd.to_numeric(f.close,errors="coerce").pct_change().rolling(20).mean())
        z=pd.concat(comps,axis=1).mean(axis=1,skipna=True) if comps else pd.Series(np.nan,index=f.index); f["strength_score"]=z.rank(pct=True); f["strength_state"]="UNAVAILABLE"; f.loc[f.strength_score>=.67,"strength_state"]="STRONG"; f.loc[f.strength_score<=.33,"strength_state"]="WEAK"; f.loc[f.strength_score.between(.33,.67),"strength_state"]="NEUTRAL"; return f
