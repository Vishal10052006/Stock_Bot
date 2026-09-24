from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True, slots=True)
class PerformanceMonitoringSnapshot:
    returns: tuple[float,...]=()
    trade_pnls: tuple[float,...]=()
    equity_curve: tuple[float,...]=()
    benchmark_returns: tuple[float,...]=()
    def __post_init__(self):
        for name in ("returns","trade_pnls","equity_curve","benchmark_returns"):
            values=tuple(float(x) for x in getattr(self,name))
            if any(not math.isfinite(x) for x in values): raise ValueError(f"{name} must contain finite values")
            object.__setattr__(self,name,values)

def evaluate_performance_monitoring(snapshot):
    r,t,c,b=snapshot.returns,snapshot.trade_pnls,snapshot.equity_curve,snapshot.benchmark_returns
    out={"return_count":len(r),"trade_count":len(t),"total_return":None,"mean_return":None,"volatility":None,"max_drawdown":None,"win_rate":None,"profit_factor":None,"expectancy":None,"benchmark_mean_return":None,"active_return_mean":None}
    if r:
        out["total_return"]=math.prod(1+x for x in r)-1
        out["mean_return"]=sum(r)/len(r)
        if len(r)>1:
            m=out["mean_return"]; out["volatility"]=math.sqrt(sum((x-m)**2 for x in r)/(len(r)-1))
    if t:
        wins=[x for x in t if x>0]; losses=[-x for x in t if x<0]
        out["win_rate"]=len(wins)/len(t); out["profit_factor"]=sum(wins)/sum(losses) if losses else math.inf; out["expectancy"]=sum(t)/len(t)
    if c:
        peak=c[0]; dd=0.0
        for x in c:
            peak=max(peak,x)
            if peak>0: dd=max(dd,(peak-x)/peak)
        out["max_drawdown"]=dd
    if b:
        out["benchmark_mean_return"]=sum(b)/len(b)
        if r: out["active_return_mean"]=out["mean_return"]-out["benchmark_mean_return"]
    return out
