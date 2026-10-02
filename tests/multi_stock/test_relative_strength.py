from datetime import datetime, timedelta, timezone

import pytest

from multi_stock.contracts import StockIntelligence
from multi_stock.relative_strength import build_relative_strength


TS = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)


def obs(symbol, market, sector, ts=TS):
    return StockIntelligence(
        timestamp=ts,
        symbol=symbol,
        state="OBSERVED",
        direction="NEUTRAL",
        quality=0.5,
        analytical_context={
            "stock_vs_market_return_1": market,
            "stock_vs_sector_return_1": sector,
        },
    )


def test_m05_relative_strength_uses_existing_causal_features():
    result = build_relative_strength(
        timestamp=TS,
        universe_symbols=["TCS", "INFY", "RELIANCE"],
        observations=[
            obs("TCS", 0.02, 0.01),
            obs("INFY", -0.01, 0.03),
        ],
    )
    assert [row.symbol for row in result.rows] == ["INFY", "TCS"]
    assert result.rows[1].vs_market_1 == pytest.approx(0.02)
    assert result.rows[0].vs_sector_1 == pytest.approx(0.03)
    assert result.coverage == pytest.approx(2 / 3)
    assert result.authority == "OBSERVATION_ONLY"


def test_m05_missing_relative_features_are_not_inferred():
    result = build_relative_strength(
        timestamp=TS,
        universe_symbols=["TCS"],
        observations=[obs("TCS", None, None)],
    )
    assert result.rows == ()
    assert result.coverage == 0.0


def test_m05_future_and_duplicate_observations_fail_closed():
    future = TS + timedelta(minutes=1)
    with pytest.raises(ValueError, match="future stock observation"):
        build_relative_strength(
            timestamp=TS,
            universe_symbols=["TCS"],
            observations=[obs("TCS", 0.1, 0.2, future)],
        )

    with pytest.raises(ValueError, match="duplicate stock observation"):
        build_relative_strength(
            timestamp=TS,
            universe_symbols=["TCS"],
            observations=[obs("TCS", 0.1, 0.2), obs("TCS", 0.2, 0.3)],
        )
