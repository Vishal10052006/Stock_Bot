"""Tests for the YFinance historical market-data adapter."""

from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from market.data.historical.adapters.yfinance import (
    YFinanceHistoricalMarketDataProvider,
)
from market.data.historical.models import HistoricalDataRequest
from market.data.historical.providers import (
    HistoricalMarketDataProvider,
)


IST = ZoneInfo("Asia/Kolkata")


def make_history() -> pd.DataFrame:
    """Create deterministic Yahoo-style OHLCV data."""

    index = pd.DatetimeIndex(
        [
            datetime(2026, 1, 2, 9, 15, tzinfo=IST),
            datetime(2026, 1, 2, 9, 20, tzinfo=IST),
        ]
    )

    return pd.DataFrame(
        {
            "Open": [100.0, 103.0],
            "High": [105.0, 106.0],
            "Low": [98.0, 101.0],
            "Close": [103.0, 104.0],
            "Volume": [1000.0, 1200.0],
        },
        index=index,
    )


def make_request() -> HistoricalDataRequest:
    """Create a standard NSE five-minute request."""

    return HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )


def test_adapter_implements_provider_protocol() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    assert isinstance(
        provider,
        HistoricalMarketDataProvider,
    )


def test_nse_symbol_is_mapped_to_yahoo_symbol() -> None:
    ticker = Mock()
    ticker.history.return_value = make_history()

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ) as ticker_factory:
        provider = YFinanceHistoricalMarketDataProvider()

        bars = provider.get_bars(make_request())

    ticker_factory.assert_called_once_with("RELIANCE.NS")
    assert len(bars) == 2


def test_existing_ns_suffix_is_not_duplicated() -> None:
    ticker = Mock()
    ticker.history.return_value = make_history()

    request = HistoricalDataRequest(
        symbol="RELIANCE.NS",
        exchange="NSE",
        timeframe_minutes=5,
    )

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ) as ticker_factory:
        provider = YFinanceHistoricalMarketDataProvider()
        provider.get_bars(request)

    ticker_factory.assert_called_once_with("RELIANCE.NS")


def test_adapter_returns_canonical_candles() -> None:
    ticker = Mock()
    ticker.history.return_value = make_history()

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ):
        provider = YFinanceHistoricalMarketDataProvider()
        bars = provider.get_bars(make_request())

    assert bars[0].symbol == "RELIANCE"
    assert bars[0].exchange == "NSE"
    assert bars[0].timeframe_minutes == 5
    assert bars[0].timestamp.tzinfo is not None
    assert bars[0].open == 100.0
    assert bars[0].high == 105.0
    assert bars[0].low == 98.0
    assert bars[0].close == 103.0
    assert bars[0].volume == 1000.0


def test_five_minute_request_uses_yfinance_5m_interval() -> None:
    ticker = Mock()
    ticker.history.return_value = make_history()

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ):
        provider = YFinanceHistoricalMarketDataProvider()
        provider.get_bars(make_request())

    ticker.history.assert_called_once_with(
        interval="5m",
        auto_adjust=False,
        period="5d",
    )


def test_explicit_request_range_is_forwarded() -> None:
    ticker = Mock()
    ticker.history.return_value = make_history()

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(2026, 1, 2, 9, 15, tzinfo=IST),
        end=datetime(2026, 1, 2, 10, 0, tzinfo=IST),
    )

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ):
        provider = YFinanceHistoricalMarketDataProvider()
        provider.get_bars(request)

    ticker.history.assert_called_once_with(
        interval="5m",
        auto_adjust=False,
        start=request.start,
        end=request.end,
    )


def test_empty_history_is_rejected() -> None:
    ticker = Mock()
    ticker.history.return_value = pd.DataFrame()

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ):
        provider = YFinanceHistoricalMarketDataProvider()

        with pytest.raises(
            ValueError,
            match="returned no historical data",
        ):
            provider.get_bars(make_request())


def test_missing_ohlcv_column_is_rejected() -> None:
    history = make_history().drop(columns=["Volume"])

    ticker = Mock()
    ticker.history.return_value = history

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ):
        provider = YFinanceHistoricalMarketDataProvider()

        with pytest.raises(
            ValueError,
            match="missing required OHLCV columns",
        ):
            provider.get_bars(make_request())


def test_naive_timestamp_is_rejected() -> None:
    history = make_history()

    history.index = pd.DatetimeIndex(
        [
            datetime(2026, 1, 2, 9, 15),
            datetime(2026, 1, 2, 9, 20),
        ]
    )

    ticker = Mock()
    ticker.history.return_value = history

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ):
        provider = YFinanceHistoricalMarketDataProvider()

        with pytest.raises(
            ValueError,
            match="naive timestamp",
        ):
            provider.get_bars(make_request())


def test_invalid_numeric_ohlcv_is_rejected() -> None:
    history = make_history()
    history.loc[history.index[0], "Close"] = float("nan")

    ticker = Mock()
    ticker.history.return_value = history

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ):
        provider = YFinanceHistoricalMarketDataProvider()

        with pytest.raises(
            ValueError,
            match="invalid OHLCV data",
        ):
            provider.get_bars(make_request())


def test_provider_failure_is_wrapped() -> None:
    ticker = Mock()
    ticker.history.side_effect = RuntimeError("network down")

    with patch(
        "market.data.historical.adapters.yfinance.yf.Ticker",
        return_value=ticker,
    ):
        provider = YFinanceHistoricalMarketDataProvider()

        with pytest.raises(
            RuntimeError,
            match="historical request failed",
        ):
            provider.get_bars(make_request())


def test_non_nse_exchange_is_rejected() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="BSE",
        timeframe_minutes=5,
    )

    with pytest.raises(
        ValueError,
        match="supports NSE only",
    ):
        provider.get_bars(request)


def test_unsupported_timeframe_is_rejected() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        timeframe_minutes=7,
    )

    with pytest.raises(
        ValueError,
        match="unsupported YFinance timeframe",
    ):
        provider.get_bars(request)


def test_non_request_input_is_rejected() -> None:
    provider = YFinanceHistoricalMarketDataProvider()

    with pytest.raises(
        TypeError,
        match="HistoricalDataRequest",
    ):
        provider.get_bars("RELIANCE")  # type: ignore[arg-type]
