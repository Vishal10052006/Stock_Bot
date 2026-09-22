"""MB-11 regime transitions and MB-12 state fusion."""
from dataclasses import dataclass
import numpy as np
@dataclass(frozen=True,slots=True)
class RegimeTransition:
    previous:str|None; current:str|None; state:str
def detect_regime_transitions(regime_series,regime_column="regime"):
    if regime_column not in regime_series: raise ValueError(f"{regime_column} is required")
    x=regime_series.copy().sort_values("timestamp",kind="stable"); p=x[regime_column].shift(1); x["previous_regime"]=p; x["transition_state"]=np.select([p.isna(),x[regime_column].eq(p),x[regime_column].ne(p)],["INITIAL","STABLE","SHIFT"],default="UNAVAILABLE"); return x
def fuse_market_state(parts,*,timestamp,benchmark,quality,version="market-bot-v1",regime_override=None,regime_probability_override=None):
    from .contracts import MarketState
    a=sum(v not in (None,"UNAVAILABLE") for v in parts.values()); availability="AVAILABLE" if a==len(parts) else ("PARTIAL" if a else "UNAVAILABLE"); trend=parts.get("trend_state"); vol=parts.get("volatility_state"); breadth=parts.get("breadth_state")
    regime="HIGH_VOLATILITY" if vol=="HIGH" else ("TREND_UP" if trend=="UP" and breadth=="POSITIVE" else ("TREND_DOWN" if trend=="DOWN" and breadth=="NEGATIVE" else ("RANGE" if parts.get("range_state")=="RANGE" else ("LOW_VOLATILITY" if vol=="LOW" else "MIXED"))))
    q=min(1,max(0,float(quality))); regime=regime_override or regime; rp=q if regime_probability_override is None else float(regime_probability_override); return MarketState(timestamp=timestamp,benchmark=benchmark,regime=regime,regime_probability=rp,trend_state=trend,trend_strength=parts.get("trend_strength"),range_state=parts.get("range_state"),volatility_state=vol,breadth_state=breadth,sector_state=parts.get("sector_state"),rotation_state=parts.get("rotation_state"),correlation_state=parts.get("correlation_state"),liquidity_state=parts.get("liquidity_state"),strength_state=parts.get("strength_state"),transition_state=parts.get("transition_state"),quality=q,availability=availability,version=version)
