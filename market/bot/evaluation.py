"""Deterministic Market Bot evaluation utilities."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True, slots=True)
class RegimeEvaluation:
    observations:int
    usable_observations:int
    transition_count:int
    transition_rate:float
    regime_persistence:float
    completeness:float

def evaluate_regimes(regime_frame:pd.DataFrame)->RegimeEvaluation:
    required={"timestamp","regime"}
    missing=required.difference(regime_frame.columns)
    if missing: raise ValueError(f"missing: {sorted(missing)}")
    frame=regime_frame.sort_values("timestamp").copy()
    usable=frame["regime"].notna()
    n=int(usable.sum())
    if n==0: return RegimeEvaluation(len(frame),0,0,0.0,0.0,0.0)
    seq=frame.loc[usable,"regime"]
    transition_count=int(seq.ne(seq.shift(1)).sum()-1)
    transition_count=max(0,transition_count)
    rate=transition_count/max(n-1,1)
    return RegimeEvaluation(len(frame),n,transition_count,rate,1.0-rate,n/len(frame) if len(frame) else 0.0)

def leakage_check(features:pd.DataFrame,timestamp:str="timestamp")->None:
    if timestamp not in features.columns: raise ValueError("timestamp column required")
    ts=pd.to_datetime(features[timestamp],utc=True)
    if not ts.is_monotonic_increasing: raise ValueError("timestamps must be ordered")
    if ts.duplicated().any(): raise ValueError("duplicate timestamps detected")
    if len(features)!=len(ts): raise ValueError("feature index mismatch")

def deterministic_replay(first:pd.DataFrame,second:pd.DataFrame)->bool:
    return first.reset_index(drop=True).equals(second.reset_index(drop=True))
