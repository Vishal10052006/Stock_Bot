from __future__ import annotations
import pandas as pd
import pytest
from multi_stock.cross_asset import build_cross_asset_context

def test_cross_asset_context_is_causal_and_observation_only():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    c = build_cross_asset_context(ts, ("USDINR", "NIFTY50", "CRUDE"), {"NIFTY50": {"timestamp": ts, "return_1": 0.01}, "USDINR": {"timestamp": ts - pd.Timedelta(minutes=5), "return_1": -0.001}})
    assert c.observed_count == 2
    assert c.coverage == pytest.approx(2 / 3)
    assert c.authority == "OBSERVATION_ONLY"

def test_future_cross_asset_observation_fails_closed():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    with pytest.raises(ValueError, match="future cross-asset observation rejected"):
        build_cross_asset_context(ts, ("NIFTY50",), {"NIFTY50": {"timestamp": ts + pd.Timedelta(seconds=1), "return_1": 0.01}})

def test_unknown_cross_asset_is_rejected():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    with pytest.raises(ValueError, match="outside declared universe"):
        build_cross_asset_context(ts, ("NIFTY50",), {"BANKNIFTY": {"timestamp": ts, "return_1": 0.01}})
