from datetime import date, datetime, timezone

import pytest

from market.data.historical.nse_security import NSESecurityDailyBar


def make_bar(**overrides):
    values = {
        "symbol": "RELIANCE",
        "series": "EQ",
        "session_date": date(2026, 9, 3),
        "previous_close": 1313.1,
        "open": 1313.1,
        "high": 1316.8,
        "low": 1302.5,
        "last_traded_price": 1302.5,
        "close": 1302.5,
        "vwap": 1308.7,
        "traded_quantity": 9721454,
        "traded_value": 12722456176.5,
        "total_trades": 158231,
    }
    values.update(overrides)
    return NSESecurityDailyBar(**values)


def test_valid_nse_daily_bar():
    bar = make_bar()

    assert bar.symbol == "RELIANCE"
    assert bar.series == "EQ"
    assert bar.session_date == date(2026, 9, 3)
    assert bar.traded_quantity == 9721454
    assert bar.traded_value == 12722456176.5
    assert bar.total_trades == 158231


def test_symbol_and_series_are_normalized():
    bar = make_bar(symbol=" reliance ", series=" eq ")

    assert bar.symbol == "RELIANCE"
    assert bar.series == "EQ"


@pytest.mark.parametrize(
    "field",
    [
        "previous_close",
        "open",
        "high",
        "low",
        "last_traded_price",
        "close",
        "vwap",
    ],
)
def test_prices_must_be_positive(field):
    with pytest.raises(ValueError):
        make_bar(**{field: 0})


def test_high_cannot_be_below_low():
    with pytest.raises(ValueError):
        make_bar(high=1300.0)


def test_high_cannot_be_below_open():
    with pytest.raises(ValueError):
        make_bar(high=1310.0, open=1311.0)


def test_low_cannot_be_above_close():
    with pytest.raises(ValueError):
        make_bar(low=1310.0, close=1309.0)


def test_traded_quantity_must_be_non_negative_integer():
    with pytest.raises(ValueError):
        make_bar(traded_quantity=-1)

    with pytest.raises(TypeError):
        make_bar(traded_quantity=1.5)


def test_traded_value_must_be_non_negative_and_finite():
    with pytest.raises(ValueError):
        make_bar(traded_value=-1)

    with pytest.raises(ValueError):
        make_bar(traded_value=float("inf"))


def test_total_trades_must_be_non_negative_integer():
    with pytest.raises(ValueError):
        make_bar(total_trades=-1)

    with pytest.raises(TypeError):
        make_bar(total_trades=1.5)


def test_session_date_must_be_date_not_datetime():
    with pytest.raises(TypeError):
        make_bar(
            session_date=datetime(
                2026,
                9,
                3,
                tzinfo=timezone.utc,
            )
        )
