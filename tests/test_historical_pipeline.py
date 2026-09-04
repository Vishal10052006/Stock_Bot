"""Integration tests for historical market-data ingestion."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from market.candles.models import Candle
from market.data.historical.models import HistoricalDataRequest
from market.data.historical.pipeline import (
    HistoricalMarketDataPipeline,
)
from market.data.historical.providers import (
    StaticHistoricalMarketDataProvider,
)
from market.data.historical.storage import (
    JsonHistoricalDatasetStore,
)


IST = ZoneInfo("Asia/Kolkata")


def make_bars() -> tuple[Candle, ...]:
    return (
        Candle(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=datetime(
                2026,
                1,
                2,
                9,
                15,
                tzinfo=IST,
            ),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000.0,
        ),
        Candle(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=datetime(
                2026,
                1,
                2,
                9,
                20,
                tzinfo=IST,
            ),
            open=103.0,
            high=106.0,
            low=102.0,
            close=105.0,
            volume=1200.0,
        ),
    )


def make_request() -> HistoricalDataRequest:
    return HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )


def test_pipeline_fetches_and_validates():
    provider = StaticHistoricalMarketDataProvider(
        make_bars()
    )

    pipeline = HistoricalMarketDataPipeline(
        provider=provider,
        require_complete_sessions=False,
    )

    result = pipeline.ingest(make_request())

    assert result.dataset.symbol == "RELIANCE"
    assert result.dataset.exchange == "NSE"
    assert result.dataset.timeframe_minutes == 5
    assert len(result.dataset.bars) == 2
    assert result.validation.valid


def test_pipeline_preserves_validation_warnings():
    bars = list(make_bars())

    bars[1] = Candle(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        timestamp=datetime(
            2026,
            1,
            2,
            9,
            30,
            tzinfo=IST,
        ),
        open=103.0,
        high=106.0,
        low=102.0,
        close=105.0,
        volume=1200.0,
    )

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(bars),
        require_complete_sessions=False,
    )

    result = pipeline.ingest(make_request())

    assert result.validation.valid
    assert result.validation.warnings


def test_invalid_data_is_rejected_before_storage(
    tmp_path: Path,
):
    invalid_bars = (
        make_bars()[0],
        Candle(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=datetime(
                2026,
                1,
                2,
                9,
                10,
                tzinfo=IST,
            ),
            open=103.0,
            high=106.0,
            low=102.0,
            close=105.0,
            volume=1200.0,
        ),
    )

    path = tmp_path / "dataset.json"

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(
            invalid_bars
        ),
        store=JsonHistoricalDatasetStore(),
    )

    with pytest.raises(
        ValueError,
        match="historical dataset validation failed",
    ):
        pipeline.ingest(
            make_request(),
            destination=path,
        )

    assert not path.exists()


def test_valid_data_is_persisted(
    tmp_path: Path,
):
    path = tmp_path / "dataset.json"

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(
            make_bars()
        ),
        store=JsonHistoricalDatasetStore(),
        require_complete_sessions=False,
    )

    result = pipeline.ingest(
        make_request(),
        destination=path,
    )

    assert result.validation.valid
    assert path.exists()

    restored = JsonHistoricalDatasetStore().load(path)

    assert restored == result.dataset


def test_pipeline_requires_store_for_destination():
    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(
            make_bars()
        ),
    )

    with pytest.raises(
        ValueError,
        match="storage implementation is required",
    ):
        pipeline.ingest(
            make_request(),
            destination="dataset.json",
        )


def test_provider_failure_is_propagated():
    class FailingProvider:
        def get_bars(self, request):
            raise RuntimeError("provider unavailable")

    pipeline = HistoricalMarketDataPipeline(
        provider=FailingProvider(),
    )

    with pytest.raises(
        RuntimeError,
        match="provider unavailable",
    ):
        pipeline.ingest(make_request())


def test_provider_data_identity_is_validated():
    bars = (
        Candle(
            symbol="TCS",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=datetime(
                2026,
                1,
                2,
                9,
                15,
                tzinfo=IST,
            ),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000.0,
        ),
    )

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(bars),
    )

    with pytest.raises(
        ValueError,
        match="configured candle belongs to a different symbol",
    ):
        pipeline.ingest(make_request())


def test_destination_is_not_written_without_store(
    tmp_path: Path,
):
    destination = tmp_path / "dataset.json"

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(
            make_bars()
        ),
    )

    with pytest.raises(ValueError):
        pipeline.ingest(
            make_request(),
            destination=destination,
        )

    assert not destination.exists()


def test_validation_happens_before_store(tmp_path: Path):
    """Invalid data must never invoke the storage layer."""

    class SpyStore:
        def __init__(self):
            self.called = False

        def save(self, dataset, path):
            self.called = True

    invalid_bars = (
        make_bars()[0],
        Candle(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=datetime(
                2026,
                1,
                2,
                9,
                10,
                tzinfo=IST,
            ),
            open=103.0,
            high=106.0,
            low=102.0,
            close=105.0,
            volume=1200.0,
        ),
    )

    store = SpyStore()

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(
            invalid_bars
        ),
        store=store,
    )

    with pytest.raises(ValueError):
        pipeline.ingest(
            make_request(),
            destination=tmp_path / "dataset.json",
        )

    assert store.called is False


def test_wrong_exchange_is_rejected():
    bars = (
        Candle(
            symbol="RELIANCE",
            exchange="BSE",
            timeframe_minutes=5,
            timestamp=datetime(
                2026,
                1,
                2,
                9,
                15,
                tzinfo=IST,
            ),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000.0,
        ),
    )

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(bars),
    )

    with pytest.raises(
        ValueError,
        match="configured candle belongs to a different exchange",
    ):
        pipeline.ingest(make_request())


def test_wrong_timeframe_is_rejected():
    bars = (
        Candle(
            symbol="RELIANCE",
            exchange="NSE",
            timeframe_minutes=15,
            timestamp=datetime(
                2026,
                1,
                2,
                9,
                15,
                tzinfo=IST,
            ),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000.0,
        ),
    )

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(bars),
    )

    with pytest.raises(
        ValueError,
        match="configured candle has a different timeframe",
    ):
        pipeline.ingest(make_request())


def test_out_of_order_data_is_rejected():
    bars = (
        make_bars()[1],
        make_bars()[0],
    )

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(bars),
    )

    with pytest.raises(
        ValueError,
        match="historical dataset validation failed",
    ):
        pipeline.ingest(make_request())


def test_storage_failure_is_propagated():
    class FailingStore:
        def save(self, dataset, path):
            raise OSError("disk unavailable")

    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(
            make_bars()
        ),
        store=FailingStore(),
        require_complete_sessions=False,
    )

    with pytest.raises(
        OSError,
        match="disk unavailable",
    ):
        pipeline.ingest(
            make_request(),
            destination="dataset.json",
        )


def test_empty_provider_data_is_rejected():
    pipeline = HistoricalMarketDataPipeline(
        provider=StaticHistoricalMarketDataProvider(()),
    )

    with pytest.raises(
        ValueError,
        match="historical dataset validation failed",
    ):
        pipeline.ingest(make_request())


def test_provider_non_sequence_result_is_rejected():
    class GeneratorProvider:
        def get_bars(self, request):
            yield from make_bars()

    pipeline = HistoricalMarketDataPipeline(
        provider=GeneratorProvider(),
    )

    with pytest.raises(
        TypeError,
        match="Sequence of Candle objects",
    ):
        pipeline.ingest(make_request())


def test_upstox_historical_provider_integrates_with_pipeline(tmp_path):
    """The Upstox provider must pass through the canonical pipeline."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from market.data.historical.adapters.upstox import (
        UpstoxHistoricalMarketDataProvider,
    )
    from market.data.historical.models import HistoricalDataRequest
    from market.data.historical.pipeline import (
        HistoricalMarketDataPipeline,
    )
    from market.data.historical.providers import (
        HistoricalDataPurpose,
    )
    from market.data.historical.storage import (
        JsonHistoricalDatasetStore,
    )
    from market.data.ingestion.providers.upstox.instrument_mapper import (
        UpstoxInstrumentMapper,
    )

    class FakeResponse:
        status_code = 200
        ok = True

        def json(self):
            return {
                "status": "success",
                "data": {
                    "candles": [
                        [
                            "2026-09-01T09:15:00+05:30",
                            100.0,
                            101.0,
                            99.0,
                            100.5,
                            10000,
                            0,
                        ],
                        [
                            "2026-09-01T09:20:00+05:30",
                            100.5,
                            102.0,
                            100.0,
                            101.5,
                            12000,
                            0,
                        ],
                    ]
                },
            }

    class FakeSession:
        def __init__(self):
            self.url = None
            self.headers = None
            self.timeout = None

        def get(self, url, *, headers, timeout):
            self.url = url
            self.headers = headers
            self.timeout = timeout
            return FakeResponse()

    session = FakeSession()

    provider = UpstoxHistoricalMarketDataProvider(
        "test-access-token",
        UpstoxInstrumentMapper(
            {"RELIANCE": "NSE_EQ|INE002A01018"}
        ),
        session=session,
        base_url="https://example.test/v3/historical-candle",
    )

    store = JsonHistoricalDatasetStore()

    pipeline = HistoricalMarketDataPipeline(
        provider=provider,
        store=store,
        require_complete_sessions=False,
        purpose=HistoricalDataPurpose.CANONICAL,
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(
            2026,
            9,
            1,
            9,
            15,
            tzinfo=ZoneInfo("Asia/Kolkata"),
        ),
        end=datetime(
            2026,
            9,
            1,
            15,
            30,
            tzinfo=ZoneInfo("Asia/Kolkata"),
        ),
    )

    destination = tmp_path / "reliance.json"

    result = pipeline.ingest(
        request,
        destination=destination,
    )

    assert result.validation.valid is True
    assert result.dataset.symbol == "RELIANCE"
    assert result.dataset.exchange == "NSE"
    assert result.dataset.timeframe_minutes == 5
    assert len(result.dataset.bars) == 2

    assert destination.exists()

    assert session.headers["Authorization"] == (
        "Bearer test-access-token"
    )
    assert session.timeout == 10.0
