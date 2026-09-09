"""Tests for point-in-time historical liquidity measurements."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from market.candles.models import Candle
from market.data.historical.liquidity import (
    DailyLiquidity,
    daily_liquidity,
    rolling_liquidity,
)


IST = ZoneInfo("Asia/Kolkata")


def make_session_candles(
    session_date: date,
    *,
    count: int = 75,
    volume: float = 1000.0,
) -> list[Candle]:
    """Create deterministic five-minute NSE session candles."""
    candles: list[Candle] = []

    for index in range(count):
        total_minutes = 9 * 60 + 15 + index * 5
        hour, minute = divmod(total_minutes, 60)

        candles.append(
            Candle(
                symbol="RELIANCE",
                exchange="NSE",
                timeframe_minutes=5,
                timestamp=datetime.combine(
                    session_date,
                    time(hour, minute),
                    tzinfo=IST,
                ),
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=volume,
            )
        )

    return candles


def test_daily_liquidity_requires_complete_session():
    candles = make_session_candles(
        date(2026, 9, 3),
        count=74,
    )

    with pytest.raises(ValueError, match="complete session"):
        daily_liquidity(
            candles,
            session_date=date(2026, 9, 3),
        )


def test_daily_liquidity_calculates_traded_value():
    candles = make_session_candles(
        date(2026, 9, 3),
    )

    # Typical price = (102 + 99 + 101) / 3 = 100.666...
    expected = 75 * ((102.0 + 99.0 + 101.0) / 3.0) * 1000.0

    result = daily_liquidity(
        candles,
        session_date=date(2026, 9, 3),
    )

    assert isinstance(result, DailyLiquidity)
    assert result.observation_count == 75
    assert result.traded_value == pytest.approx(expected)


def test_rolling_liquidity_excludes_as_of_session():
    previous = DailyLiquidity(
        session_date=date(2026, 9, 1),
        observation_count=75,
        source="5m_ohlcv",
        traded_value=100.0,
    )
    current = DailyLiquidity(
        session_date=date(2026, 9, 2),
        observation_count=75,
        source="5m_ohlcv",
        traded_value=1000.0,
    )

    result = rolling_liquidity(
        (previous, current),
        as_of=date(2026, 9, 2),
        lookback_sessions=20,
    )

    assert result.completed_sessions == (previous,)
    assert result.average_traded_value == pytest.approx(100.0)


def test_rolling_liquidity_uses_latest_completed_sessions():
    sessions = tuple(
        DailyLiquidity(
            session_date=date(2026, 8, day),
            observation_count=75,
        source="5m_ohlcv",
            traded_value=float(day),
        )
        for day in range(1, 6)
    )

    result = rolling_liquidity(
        sessions,
        as_of=date(2026, 8, 10),
        lookback_sessions=3,
    )

    assert tuple(
        session.session_date
        for session in result.completed_sessions
    ) == (
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
    )

    assert result.average_traded_value == pytest.approx(4.0)


def test_rolling_liquidity_returns_none_without_history():
    result = rolling_liquidity(
        (),
        as_of=date(2026, 9, 5),
        lookback_sessions=20,
    )

    assert result.completed_sessions == ()
    assert result.average_traded_value is None


def test_daily_liquidity_rejects_mixed_instruments():
    candles = make_session_candles(date(2026, 9, 3))

    mixed = list(candles)
    mixed[-1] = Candle(
        symbol="INFY",
        exchange="NSE",
        timeframe_minutes=5,
        timestamp=mixed[-1].timestamp,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1000.0,
    )

    with pytest.raises(ValueError, match="exactly one"):
        daily_liquidity(
            mixed,
            session_date=date(2026, 9, 3),
        )


def test_daily_liquidity_rejects_duplicate_timestamps():
    candles = make_session_candles(date(2026, 9, 3))

    duplicated = list(candles)
    duplicated[-1] = duplicated[-2]

    with pytest.raises(ValueError, match="duplicate timestamps"):
        daily_liquidity(
            duplicated,
            session_date=date(2026, 9, 3),
        )


def test_daily_liquidity_rejects_out_of_order_timestamps():
    candles = make_session_candles(date(2026, 9, 3))

    unordered = list(candles)
    unordered[10], unordered[11] = unordered[11], unordered[10]

    with pytest.raises(ValueError, match="chronological"):
        daily_liquidity(
            unordered,
            session_date=date(2026, 9, 3),
        )


def test_rolling_liquidity_rejects_out_of_order_sessions():
    sessions = (
        DailyLiquidity(
            session_date=date(2026, 9, 3),
            observation_count=75,
        source="5m_ohlcv",
            traded_value=300.0,
        ),
        DailyLiquidity(
            session_date=date(2026, 9, 2),
            observation_count=75,
        source="5m_ohlcv",
            traded_value=200.0,
        ),
    )

    with pytest.raises(ValueError, match="chronological"):
        rolling_liquidity(
            sessions,
            as_of=date(2026, 9, 5),
        )


def test_rolling_liquidity_rejects_duplicate_sessions():
    session = DailyLiquidity(
        session_date=date(2026, 9, 3),
        observation_count=75,
        source="5m_ohlcv",
        traded_value=300.0,
    )

    with pytest.raises(ValueError, match="duplicate dates"):
        rolling_liquidity(
            (session, session),
            as_of=date(2026, 9, 5),
        )


def test_rolling_liquidity_never_accepts_as_of_session_in_measurement():
    session = DailyLiquidity(
        session_date=date(2026, 9, 5),
        observation_count=75,
        source="5m_ohlcv",
        traded_value=999999.0,
    )

    measurement = rolling_liquidity(
        (session,),
        as_of=date(2026, 9, 5),
    )

    assert measurement.completed_sessions == ()
    assert measurement.average_traded_value is None


def test_liquidity_measurement_rejects_session_at_or_after_as_of():
    session = DailyLiquidity(
        session_date=date(2026, 9, 6),
        observation_count=75,
        source="5m_ohlcv",
        traded_value=100.0,
    )

    with pytest.raises(ValueError, match="before as_of"):
        from market.data.historical.liquidity import LiquidityMeasurement

        LiquidityMeasurement(
            as_of=date(2026, 9, 5),
            lookback_sessions=20,
            completed_sessions=(session,),
            average_traded_value=100.0,
        )


def make_measurement(
    *,
    average: float | None,
    completed: int,
    lookback: int = 20,
):
    from datetime import date

    from market.data.historical.liquidity import (
        DailyLiquidity,
        LiquidityMeasurement,
    )

    sessions = tuple(
        DailyLiquidity(
            session_date=date(2026, 8, day),
            observation_count=75,
        source="5m_ohlcv",
            traded_value=average if average is not None else 0.0,
        )
        for day in range(1, completed + 1)
    )

    return LiquidityMeasurement(
        as_of=date(2026, 9, 1),
        lookback_sessions=lookback,
        completed_sessions=sessions,
        average_traded_value=average,
    )


def test_liquidity_policy_accepts_threshold_exactly():
    from market.data.historical.liquidity import LiquidityPolicy

    policy = LiquidityPolicy(
        version="v1.0",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=1000.0,
    )

    measurement = make_measurement(
        average=1000.0,
        completed=20,
    )

    from market.data.historical.liquidity import is_liquid

    assert is_liquid(measurement, policy) is True


def test_liquidity_policy_rejects_value_below_threshold():
    from market.data.historical.liquidity import (
        LiquidityPolicy,
        is_liquid,
    )

    policy = LiquidityPolicy(
        version="v1.0",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=1000.0,
    )

    measurement = make_measurement(
        average=999.99,
        completed=20,
    )

    assert is_liquid(measurement, policy) is False


def test_liquidity_policy_rejects_insufficient_history():
    from market.data.historical.liquidity import (
        LiquidityPolicy,
        is_liquid,
    )

    policy = LiquidityPolicy(
        version="v1.0",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=1000.0,
    )

    measurement = make_measurement(
        average=5000.0,
        completed=19,
    )

    assert is_liquid(measurement, policy) is False


def test_liquidity_policy_rejects_missing_average():
    from market.data.historical.liquidity import (
        LiquidityPolicy,
        is_liquid,
    )

    policy = LiquidityPolicy(
        version="v1.0",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=1000.0,
    )

    measurement = make_measurement(
        average=None,
        completed=20,
    )

    assert is_liquid(measurement, policy) is False


def test_liquidity_policy_rejects_mismatched_lookback():
    from market.data.historical.liquidity import (
        LiquidityPolicy,
        is_liquid,
    )

    policy = LiquidityPolicy(
        version="v1.0",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=1000.0,
    )

    measurement = make_measurement(
        average=5000.0,
        completed=10,
        lookback=10,
    )

    with pytest.raises(ValueError, match="lookback"):
        is_liquid(measurement, policy)


def test_liquidity_policy_rejects_invalid_configuration():
    from market.data.historical.liquidity import LiquidityPolicy

    with pytest.raises(ValueError, match="minimum_completed_sessions"):
        LiquidityPolicy(
            version="v1.0",
            lookback_sessions=20,
            minimum_completed_sessions=21,
            minimum_average_traded_value=1000.0,
        )

    with pytest.raises(ValueError, match="minimum_average_traded_value"):
        LiquidityPolicy(
            version="v1.0",
            lookback_sessions=20,
            minimum_completed_sessions=20,
            minimum_average_traded_value=-1.0,
        )


def test_liquidity_policy_is_immutable():
    from market.data.historical.liquidity import LiquidityPolicy

    policy = LiquidityPolicy(
        version="v1.0",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=1000.0,
    )

    with pytest.raises(AttributeError):
        policy.version = "v2.0"


def test_nse_security_daily_liquidity_uses_exchange_reported_value():
    from market.data.historical.nse_security import NSESecurityDailyBar
    from market.data.historical.liquidity import (
        daily_liquidity_from_nse,
    )

    bar = NSESecurityDailyBar(
        symbol="RELIANCE",
        series="EQ",
        session_date=date(2026, 9, 3),
        previous_close=1313.1,
        open=1313.1,
        high=1316.8,
        low=1302.5,
        last_traded_price=1302.5,
        close=1302.5,
        vwap=1308.7,
        traded_quantity=9721454,
        traded_value=12722456176.5,
        total_trades=158231,
    )

    result = daily_liquidity_from_nse(bar)

    assert isinstance(result, DailyLiquidity)
    assert result.session_date == date(2026, 9, 3)
    assert result.observation_count == 1
    assert result.traded_value == 12722456176.5
    assert result.source == "nse_security_daily"


def test_nse_security_daily_liquidity_does_not_recalculate_value():
    from market.data.historical.nse_security import NSESecurityDailyBar
    from market.data.historical.liquidity import (
        daily_liquidity_from_nse,
    )

    bar = NSESecurityDailyBar(
        symbol="RELIANCE",
        series="EQ",
        session_date=date(2026, 9, 3),
        previous_close=100.0,
        open=100.0,
        high=110.0,
        low=90.0,
        last_traded_price=105.0,
        close=105.0,
        vwap=101.0,
        traded_quantity=1000,
        traded_value=123456.78,
        total_trades=50,
    )

    result = daily_liquidity_from_nse(bar)

    assert result.traded_value == 123456.78


def test_nse_security_daily_liquidity_rejects_wrong_type():
    from market.data.historical.liquidity import (
        daily_liquidity_from_nse,
    )

    with pytest.raises(TypeError, match="NSESecurityDailyBar"):
        daily_liquidity_from_nse(object())
