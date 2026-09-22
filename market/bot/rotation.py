"""Causal sector rotation classification."""
from __future__ import annotations
import pandas as pd

class SectorRotationEngine:
    def __init__(self, improvement_threshold: float=0.10) -> None:
        if improvement_threshold<=0: raise ValueError("improvement_threshold must be positive")
        self.improvement_threshold=improvement_threshold

    def calculate(self, ranked: pd.DataFrame) -> pd.DataFrame:
        required={"timestamp","sector","sector_strength_pct"}
        missing=required.difference(ranked.columns)
        if missing: raise ValueError(f"missing: {sorted(missing)}")
        frame=ranked.copy().sort_values(["sector","timestamp"],kind="stable")
        frame["strength_change"]=frame.groupby("sector",sort=False)["sector_strength_pct"].diff()
        frame["rotation_state"]="STABLE"
        frame.loc[frame["strength_change"]>=self.improvement_threshold,"rotation_state"]="IMPROVING"
        frame.loc[frame["strength_change"]<=-self.improvement_threshold,"rotation_state"]="WEAKENING"
        return frame

    def summarize(self, rotation: pd.DataFrame) -> pd.DataFrame:
        rows=[]
        for timestamp,group in rotation.groupby("timestamp",sort=True):
            rows.append({
                "timestamp":timestamp,
                "strong_sectors":group.nlargest(3,"sector_strength_pct")["sector"].tolist(),
                "weak_sectors":group.nsmallest(3,"sector_strength_pct")["sector"].tolist(),
                "improving_sectors":group.loc[group["rotation_state"]=="IMPROVING","sector"].tolist(),
                "weakening_sectors":group.loc[group["rotation_state"]=="WEAKENING","sector"].tolist(),
            })
        return pd.DataFrame(rows)
