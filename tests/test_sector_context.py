from __future__ import annotations

from datetime import date

import pandas as pd
from unittest.mock import patch

from market.candles.models import Candle
from market.data.context.models import SectorMapping
from market.data.context.sector_context import (
    build_sector_context,
    candles_to_context_frame,
)
from market.data.context.sector_registry import (
    DEFAULT_YFINANCE_INDEX_SYMBOLS,
    SECTOR_INDEX_SYMBOLS,
    provider_symbols_for,
)
from market.data.historical.adapters.yfinance_index import (
    YFinanceHistoricalIndexMarketDataProvider,
)
from market.data.historical.models import HistoricalDataRequest


def test_sector_registry_contains_core_indices() -> None:
    expected = {
        "NIFTY_AUTO",
        "NIFTY_BANK",
        "NIFTY_FINANCIAL_SERVICES",
        "NIFTY_FMCG",
        "NIFTY_IT",
        "NIFTY_MEDIA",
        "NIFTY_METAL",
        "NIFTY_PHARMA",
        "NIFTY_PSU_BANK",
        "NIFTY_REALTY",
        "NIFTY_OIL_AND_GAS",
    }

    assert expected.issubset(set(SECTOR_INDEX_SYMBOLS))
    assert DEFAULT_YFINANCE_INDEX_SYMBOLS["NIFTY50"] == "^NSEI"


def test_provider_symbols_for_rejects_unknown_index() -> None:
    try:
        provider_symbols_for(("NIFTY_UNKNOWN",))
    except ValueError as exc:
        assert "NIFTY_UNKNOWN" in str(exc)
    else:
        raise AssertionError("unknown sector index was accepted")


def test_yfinance_provider_uses_central_sector_registry() -> None:
    provider = YFinanceHistoricalIndexMarketDataProvider()

    request = HistoricalDataRequest(
        symbol="NIFTY_IT",
        exchange="NSE",
        timeframe_minutes=5,
    )

    assert provider.provider_symbols["NIFTY_IT"] == "^CNXIT"
    assert provider.provider_symbols["NIFTY_BANK"] == "^NSEBANK"
    assert provider.provenance(request)["provider_symbol"] == "^CNXIT"


def test_candles_to_context_frame_preserves_key_and_timezone() -> None:
    ts = pd.Timestamp(
        "2026-09-11 09:15:00",
        tz="Asia/Kolkata",
    ).to_pydatetime()

    bars = (
        Candle(
            symbol="NIFTY_IT",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=ts,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=0.0,
        ),
    )

    frame = candles_to_context_frame(bars)

    assert frame.loc[0, "sector_index_symbol"] == "NIFTY_IT"
    assert frame.loc[0, "close"] == 100.5
    assert isinstance(frame["timestamp"].dtype, pd.DatetimeTZDtype)


def test_build_sector_context_fetches_each_requested_index() -> None:
    ts = pd.Timestamp(
        "2026-09-11 09:15:00",
        tz="Asia/Kolkata",
    ).to_pydatetime()

    def fake_bars(request: HistoricalDataRequest):
        return (
            Candle(
                symbol=request.symbol,
                exchange="NSE",
                timeframe_minutes=5,
                timestamp=ts,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=0.0,
            ),
            Candle(
                symbol=request.symbol,
                exchange="NSE",
                timeframe_minutes=5,
                timestamp=ts.replace(minute=20),
                open=100.5,
                high=101.5,
                low=100.0,
                close=101.0,
                volume=0.0,
            ),
        )

    provider = YFinanceHistoricalIndexMarketDataProvider(
        provider_symbols={
            "NIFTY_IT": "^CNXIT",
            "NIFTY_BANK": "^NSEBANK",
        },
    )

    with patch.object(provider, "get_bars", side_effect=fake_bars):
        result = build_sector_context(
            provider,
            symbols=("NIFTY_IT", "NIFTY_BANK"),
            timeframe_minutes=5,
        )

    assert set(result["sector_index_symbol"]) == {"NIFTY_IT", "NIFTY_BANK"}
    assert {
        "return_1",
        "return_3",
        "return_12",
        "volatility_20",
    }.issubset(result.columns)


def test_sector_mapping_is_explicitly_point_in_time() -> None:
    mapping = SectorMapping(
        symbol="RELIANCE",
        sector_index_symbol="NIFTY_OIL_AND_GAS",
        effective_from=date(2026, 9, 9),
    )

    assert mapping.effective_from == date(2026, 9, 9)
