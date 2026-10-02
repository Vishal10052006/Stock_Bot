from datetime import datetime, timezone

import pytest

from multi_stock.breadth import build_market_breadth
from multi_stock.contracts import StockIntelligence


TS = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)


def obs(symbol, value, ts=TS):
    return StockIntelligence(
        timestamp=ts,
        symbol=symbol,
        state="OBSERVED",
        direction="NEUTRAL",
        quality=0.5,
        analytical_context={"return_1": value},
    )


def test_m03_market_breadth_is_deterministic_and_descriptive():
    result = build_market_breadth(
        timestamp=TS,
        universe_symbols=["RELIANCE", "TCS", "INFY", "HDFC"],
        observations=[obs("TCS", 0.02), obs("INFY", -0.01), obs("HDFC", 0.0)],
    )
    assert result.advances == 1
    assert result.declines == 1
    assert result.unchanged == 1
    assert result.observed_count == 3
    assert result.coverage == pytest.approx(0.75)
    assert result.breadth_ratio == pytest.approx(0.0)
    assert result.advance_decline_ratio == pytest.approx(1.0)
    assert result.authority == "OBSERVATION_ONLY"


def test_m03_missing_returns_are_not_inferred():
    result = build_market_breadth(
        timestamp=TS,
        universe_symbols=["TCS", "INFY"],
        observations=[obs("TCS", None)],
    )
    assert result.observed_count == 0
    assert result.breadth_ratio is None


def test_m03_future_and_duplicate_observations_fail_closed():
    with pytest.raises(ValueError, match="future stock observation"):
        build_market_breadth(
            timestamp=TS,
            universe_symbols=["TCS"],
            observations=[obs("TCS", 0.1, datetime(2026, 10, 2, 11, tzinfo=timezone.utc))],
        )

    with pytest.raises(ValueError, match="duplicate stock observation"):
        build_market_breadth(
            timestamp=TS,
            universe_symbols=["TCS"],
            observations=[obs("TCS", 0.1), obs("TCS", 0.2)],
        )
