"""Adapter to the existing Phase 6 causal regime detector; no duplicate regime engine."""
import numpy as np
import pandas as pd
from market.regime.detector import detect_market_regime
def detect_benchmark_regime(benchmark_frame):
    if benchmark_frame.empty: return pd.DataFrame(columns=["timestamp","regime","regime_probability"])
    x=benchmark_frame.copy().sort_values("timestamp",kind="stable"); c=pd.to_numeric(x.close,errors="coerce"); x["market_return_3"]=c.pct_change(3); x["market_return_12"]=c.pct_change(12); x["market_volatility_20"]=c.pct_change().rolling(20).std()*np.sqrt(252)
    return detect_market_regime(x[["timestamp","market_return_3","market_return_12","market_volatility_20"]])
