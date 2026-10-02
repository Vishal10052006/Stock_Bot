from datetime import date, datetime, timezone
import pytest
from market.data.historical.liquidity import DailyLiquidity, LiquidityMeasurement
from multi_stock.liquidity import build_liquidity_snapshot

TS = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)

def measurement(as_of, value):
    return LiquidityMeasurement(
        as_of=as_of,
        lookback_sessions=20,
        completed_sessions=(
            DailyLiquidity(as_of.replace(day=1), 1, value, "test"),
        ),
        average_traded_value=value,
    )

def test_m06_liquidity_is_deterministic_and_observation_only():
    result = build_liquidity_snapshot(
        timestamp=TS, universe_symbols=["TCS", "INFY", "RELIANCE"],
        measurements={
            "TCS": measurement(date(2026, 10, 1), 1200000),
            "INFY": measurement(date(2026, 10, 1), 900000),
        },
    )
    assert result.symbols == ("INFY", "RELIANCE", "TCS")
    assert result.traded_value["TCS"] == pytest.approx(1200000)
    assert result.traded_value["RELIANCE"] is None
    assert result.coverage == pytest.approx(2 / 3)
    assert result.authority == "OBSERVATION_ONLY"

def test_m06_future_liquidity_is_rejected():
    with pytest.raises(ValueError, match="future liquidity"):
        build_liquidity_snapshot(
            timestamp=TS, universe_symbols=["TCS"],
            measurements={"TCS": measurement(date(2026, 10, 3), 100)},
        )

def test_m06_invalid_measurement_symbol_is_rejected():
    with pytest.raises(ValueError, match="outside universe"):
        build_liquidity_snapshot(
            timestamp=TS, universe_symbols=["TCS"],
            measurements={"INFY": measurement(date(2026, 10, 1), 100)},
        )
