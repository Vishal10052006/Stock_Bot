"""Tests for Phase 2 historical-data contracts."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from market.candles.models import Candle
from market.data.historical.corporate_actions import (
    CorporateAction,
    CorporateActionType,
)
from market.data.historical.models import (
    HistoricalDataRequest,
    HistoricalDataset,
)
from market.data.historical.providers import (
    HistoricalMarketDataProvider,
    StaticHistoricalMarketDataProvider,
)


IST = ZoneInfo("Asia/Kolkata")


def make_candle(
    symbol: str = "RELIANCE",
    exchange: str = "NSE",
    timeframe_minutes: int = 5,
) -> Candle:
    return Candle(
        symbol=symbol,
        exchange=exchange,
        timeframe_minutes=timeframe_minutes,
        timestamp=datetime(2026, 1, 2, 9, 15, tzinfo=IST),
        open=100.0,
        high=105.0,
        low=98.0,
        close=103.0,
        volume=1000.0,
    )


def test_historical_request_defaults_to_nse_five_minutes() -> None:
    request = HistoricalDataRequest(symbol="RELIANCE")

    assert request.exchange == "NSE"
    assert request.timeframe_minutes == 5


def test_historical_request_requires_timezone_aware_range() -> None:
    with pytest.raises(ValueError, match="start must be timezone-aware"):
        HistoricalDataRequest(
            symbol="RELIANCE",
            start=datetime(2026, 1, 2, 9, 15),
        )


def test_historical_request_rejects_reverse_range() -> None:
    with pytest.raises(ValueError, match="end must be after start"):
        HistoricalDataRequest(
            symbol="RELIANCE",
            start=datetime(2026, 1, 2, 10, 0, tzinfo=IST),
            end=datetime(2026, 1, 2, 9, 15, tzinfo=IST),
        )


def test_historical_dataset_accepts_canonical_candles() -> None:
    candle = make_candle()

    dataset = HistoricalDataset(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        bars=(candle,),
        metadata={"provider": "test"},
    )

    assert dataset.symbol == "RELIANCE"
    assert dataset.exchange == "NSE"
    assert dataset.timeframe_minutes == 5
    assert dataset.bars == (candle,)
    assert dataset.metadata["provider"] == "test"


def test_historical_dataset_defaults_to_no_corporate_actions() -> None:
    dataset = HistoricalDataset(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        bars=(make_candle(),),
        metadata={"provider": "test"},
    )

    assert dataset.corporate_actions == ()


def test_historical_dataset_accepts_corporate_actions() -> None:
    action = CorporateAction(
        isin="INE002A01018",
        action_type=CorporateActionType.DIVIDEND,
        ex_date=date(2026, 8, 27),
        source="upstox",
    )

    dataset = HistoricalDataset(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        bars=(make_candle(),),
        metadata={"provider": "test"},
        corporate_actions=(action,),
    )

    assert dataset.corporate_actions == (action,)


def test_historical_dataset_rejects_invalid_corporate_action() -> None:
    with pytest.raises(
        TypeError,
        match=r"corporate_actions\[0\] must be a CorporateAction",
    ):
        HistoricalDataset(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=5,
            bars=(make_candle(),),
            metadata={"provider": "test"},
            corporate_actions=("invalid",),
        )


def test_historical_dataset_rejects_wrong_symbol() -> None:
    candle = make_candle(symbol="TCS")

    with pytest.raises(
        ValueError,
        match="different symbol",
    ):
        HistoricalDataset(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=5,
            bars=(candle,),
            metadata={},
        )


def test_historical_dataset_rejects_wrong_timeframe() -> None:
    candle = make_candle(timeframe_minutes=15)

    with pytest.raises(
        ValueError,
        match="different timeframe",
    ):
        HistoricalDataset(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=5,
            bars=(candle,),
            metadata={},
        )


def test_metadata_is_immutable() -> None:
    dataset = HistoricalDataset(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        bars=(make_candle(),),
        metadata={"provider": "test"},
    )

    with pytest.raises(TypeError):
        dataset.metadata["provider"] = "changed"


def test_static_provider_implements_protocol() -> None:
    provider = StaticHistoricalMarketDataProvider(
        [make_candle()]
    )

    assert isinstance(
        provider,
        HistoricalMarketDataProvider,
    )


def test_static_provider_returns_canonical_candles() -> None:
    candle = make_candle()
    provider = StaticHistoricalMarketDataProvider([candle])

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    assert provider.get_bars(request) == (candle,)


def test_static_provider_rejects_symbol_mismatch() -> None:
    provider = StaticHistoricalMarketDataProvider(
        [make_candle(symbol="TCS")]
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    with pytest.raises(ValueError, match="different symbol"):
        provider.get_bars(request)


def test_historical_dataset_accepts_instrument_status_timeline():
    from datetime import date

    from market.data.historical.instrument_status import (
        InstrumentStatus,
        InstrumentStatusTimeline,
        InstrumentStatusType,
    )

    timeline = InstrumentStatusTimeline(
        (
            InstrumentStatus(
                symbol="RELIANCE",
                status=InstrumentStatusType.SUSPENDED,
                effective_from=date(2026, 1, 2),
            ),
        )
    )

    dataset = HistoricalDataset(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        bars=(make_candle(),),
        metadata={},
        instrument_status=timeline,
    )

    assert dataset.instrument_status is timeline


def test_historical_dataset_rejects_status_timeline_for_different_symbol():
    from datetime import date

    from market.data.historical.instrument_status import (
        InstrumentStatus,
        InstrumentStatusTimeline,
        InstrumentStatusType,
    )

    timeline = InstrumentStatusTimeline(
        (
            InstrumentStatus(
                symbol="TCS",
                status=InstrumentStatusType.ACTIVE,
                effective_from=date(2026, 1, 1),
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="different symbol",
    ):
        HistoricalDataset(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=5,
            bars=(make_candle(),),
            metadata={},
            instrument_status=timeline,
        )
