"""MB-18 walk-forward regime research; research-only."""
from dataclasses import dataclass
import numpy as np
@dataclass(frozen=True,slots=True)
class RegimeResearchResult:
    folds:int; accuracy:float|None; used_features:tuple[str,...]; status:str
def walk_forward_regime_experiment(data,feature_columns,target_column="regime",min_train=200,test_size=50):
    x=data.sort_values("timestamp",kind="stable").copy(); features=[c for c in feature_columns if c in x.columns]
    if not features or target_column not in x: return RegimeResearchResult(0,None,tuple(features),"INSUFFICIENT_DATA")
    scores=[]; start=min_train
    while start+test_size<=len(x):
        train=x.iloc[:start].dropna(subset=features+[target_column]); test=x.iloc[start:start+test_size].dropna(subset=features+[target_column])
        if len(train)>=min_train and len(test):
            from sklearn.linear_model import LogisticRegression
            m=LogisticRegression(max_iter=1000); m.fit(train[features],train[target_column]); scores.extend((m.predict(test[features])==test[target_column].to_numpy()).tolist())
        start+=test_size
    return RegimeResearchResult(len(scores),float(np.mean(scores)) if scores else None,tuple(features),"RESEARCH_ONLY" if scores else "INSUFFICIENT_DATA")
