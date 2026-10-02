from __future__ import annotations
from datetime import datetime, timezone
import pytest
from intelligence.analysis.contracts import AnalysisContext
from multi_stock import MultiStockIntelligence

def ctx(symbol: str, minute: int = 0) -> AnalysisContext:
    return AnalysisContext(
        timestamp=datetime(2026,10,2,10,minute,tzinfo=timezone.utc),
        symbol=symbol, technical_context={}, structure_context={}, volume_context={},
        volatility_context={}, market_context={}, sector_context={}, relative_performance={},
        research_context={}, feature_vector={"x":1.0}, analytical_direction="BULLISH",
        analytical_state="ALIGNED", candidates=(), quality={"score":0.8},
        analysis_version="v1.0", feature_version="v1.0", data_version="d1",
        provenance={"source":"test"},
    )

def test_multistock_context_is_deterministic():
    c=MultiStockIntelligence().build(
        timestamp=datetime(2026,10,2,10,5,tzinfo=timezone.utc),
        universe_symbols=["TCS","RELIANCE","INFY"], stock_contexts=[ctx("INFY"),ctx("TCS")],
        universe_version="u1", data_version="d1")
    assert c.universe_symbols == ("INFY","RELIANCE","TCS")
    assert c.observation.available_count == 2
    assert c.observation.unavailable_count == 1
    assert c.observation.coverage == pytest.approx(2/3)
    assert c.observation.direction_counts == {"BULLISH":2}

def test_future_context_fails_closed():
    with pytest.raises(ValueError, match="future stock context"):
        MultiStockIntelligence().build(
            timestamp=datetime(2026,10,2,10,tzinfo=timezone.utc),
            universe_symbols=["TCS"], stock_contexts=[ctx("TCS",1)])

def test_duplicate_and_outside_universe_fail_closed():
    engine=MultiStockIntelligence()
    with pytest.raises(ValueError, match="duplicate stock context"):
        engine.build(timestamp=datetime(2026,10,2,10,tzinfo=timezone.utc),
                     universe_symbols=["TCS"], stock_contexts=[ctx("TCS"),ctx("TCS")])
    with pytest.raises(ValueError, match="outside declared universe"):
        engine.build(timestamp=datetime(2026,10,2,10,tzinfo=timezone.utc),
                     universe_symbols=["TCS"], stock_contexts=[ctx("INFY")])

def test_mapping_adapter_preserves_observation_authority():
    c=MultiStockIntelligence().build(
        timestamp=datetime(2026,10,2,10,tzinfo=timezone.utc),
        universe_symbols=["TCS"],
        stock_contexts=[{"timestamp":datetime(2026,10,2,10,tzinfo=timezone.utc),
                         "symbol":"TCS","direction":"NEUTRAL","state":"AVAILABLE",
                         "provenance":{"source":"mapping"}}])
    assert c.authority == "OBSERVATION_ONLY"
    assert c.observation.observations[0].symbol == "TCS"
