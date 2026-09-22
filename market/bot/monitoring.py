"""MB-15 monitoring."""
from dataclasses import dataclass
from collections import Counter
@dataclass(frozen=True,slots=True)
class MarketBotHealth:
    status:str; availability_rate:float; sample_count:int; regime_counts:dict
def summarize_health(states):
    s=list(states); n=len(s)
    if not n: return MarketBotHealth("NO_DATA",0.0,0,{})
    rate=sum(x.availability=="AVAILABLE" for x in s)/n; status="HEALTHY" if rate>=.90 else ("DEGRADED" if rate>=.50 else "UNAVAILABLE")
    return MarketBotHealth(status,rate,n,dict(Counter(x.regime or "UNAVAILABLE" for x in s)))
