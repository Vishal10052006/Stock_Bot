"""MB-18 controlled statistical/ML regime research protocol."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any
import numpy as np
import pandas as pd

@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

@dataclass(frozen=True, slots=True)
class RegimeResearchResult:
    model_name: str
    folds: tuple[WalkForwardFold,...]
    metrics: tuple[dict[str,Any],...]
    promoted: bool=False

class RegimeResearchProtocol:
    """Run controlled time-ordered experiments without promoting a model."""

    def __init__(self, train_size:int=252, test_size:int=63, step:int=63)->None:
        if min(train_size,test_size,step)<1: raise ValueError("fold sizes must be positive")
        self.train_size=train_size; self.test_size=test_size; self.step=step

    def folds(self,data:pd.DataFrame,timestamp:str="timestamp")->tuple[WalkForwardFold,...]:
        if timestamp not in data.columns:
            raise ValueError(f"missing timestamp column: {timestamp}")
        frame=data.copy()
        frame[timestamp]=pd.to_datetime(frame[timestamp],utc=True)
        if frame[timestamp].isna().any():
            raise ValueError("timestamp contains invalid values")
        frame=frame.sort_values(timestamp,kind="stable").reset_index(drop=True)
        if frame[timestamp].duplicated().any():
            raise ValueError("timestamps must be unique")
        ts=frame[timestamp]
        out=[]
        start=self.train_size
        while start+self.test_size<=len(frame):
            out.append(WalkForwardFold(ts.iloc[start-self.train_size],ts.iloc[start-1],ts.iloc[start],ts.iloc[start+self.test_size-1]))
            start+=self.step
        return tuple(out)

    def run(self,data:pd.DataFrame,features:list[str],estimator_factory:Callable[[],Any],model_name:str)->RegimeResearchResult:
        frame=data.copy()
        frame["timestamp"]=pd.to_datetime(frame["timestamp"],utc=True)
        if frame["timestamp"].isna().any():
            raise ValueError("timestamp contains invalid values")
        frame=frame.sort_values("timestamp",kind="stable").reset_index(drop=True)
        folds=self.folds(frame)
        metrics=[]
        for fold in folds:
            train=frame.loc[(frame["timestamp"]>=fold.train_start)&(frame["timestamp"]<=fold.train_end),features]
            test=frame.loc[(frame["timestamp"]>=fold.test_start)&(frame["timestamp"]<=fold.test_end),features]
            if train.empty or test.empty: continue
            model=estimator_factory()
            model.fit(train)
            labels=model.predict(test)
            metrics.append({
                "train_rows":len(train),
                "test_rows":len(test),
                "unique_test_regimes":int(pd.Series(labels).nunique()),
                "test_timestamp_start":fold.test_start.isoformat(),
                "test_timestamp_end":fold.test_end.isoformat(),
            })
        return RegimeResearchResult(model_name=model_name,folds=folds,metrics=tuple(metrics),promoted=False)
