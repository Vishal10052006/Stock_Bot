from __future__ import annotations
from collections import Counter
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class RegimeMonitoringSnapshot:
    reference: tuple[str,...]=()
    current: tuple[str,...]=()
    def __post_init__(self):
        object.__setattr__(self,"reference",tuple(str(x) for x in self.reference))
        object.__setattr__(self,"current",tuple(str(x) for x in self.current))

def evaluate_regime_monitoring(snapshot):
    n=len(snapshot.current); rn=len(snapshot.reference)
    metrics={"reference_count":rn,"current_count":n,"unique_current_regimes":len(set(snapshot.current))}
    if not n: return metrics,()
    cur=Counter(snapshot.current); ref=Counter(snapshot.reference); alerts=[]
    for regime,count in cur.items():
        cr=count/n; rr=ref.get(regime,0)/rn if rn else 0.0
        metrics[f"regime.{regime}.rate"]=cr; metrics[f"regime.{regime}.reference_rate"]=rr
        if rn and rr==0 and cr>0.20: alerts.append("NEW_REGIME_DOMINANCE")
        elif rn and abs(cr-rr)>0.30: alerts.append("REGIME_DISTRIBUTION_SHIFT")
    return metrics,tuple(sorted(set(alerts)))
