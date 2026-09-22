"""Descriptive market-regime transition detector."""
from __future__ import annotations
import pandas as pd

class RegimeTransitionEngine:
    def calculate(self,regime_frame:pd.DataFrame)->pd.DataFrame:
        required={"timestamp","regime"}
        missing=required.difference(regime_frame.columns)
        if missing: raise ValueError(f"missing: {sorted(missing)}")
        frame=regime_frame.loc[:,["timestamp","regime"]].copy()
        frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
        frame=frame.sort_values("timestamp")
        previous=frame["regime"].shift(1)
        frame["previous_regime"]=previous
        frame["transition_state"]="NONE"
        changed=frame["regime"].notna()&previous.notna()&frame["regime"].ne(previous)
        frame.loc[changed,"transition_state"]=previous[changed].astype(str)+"->"+frame.loc[changed,"regime"].astype(str)
        return frame
