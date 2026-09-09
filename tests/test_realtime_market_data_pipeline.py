from datetime import datetime, timezone

import pytest

from market.candles.aggregator import CandleAggregator
from market.data.events import MarketEvent, MarketEventType
from market.data.ingestion import MarketFeed
from market.data.metrics import DataQualityMetrics
from market.data.validation import MarketEventValidator


class StubMarketFeed(MarketFeed):
    def __init__(self, events):
        self._events = tuple(events)
        self.connected = False
        self.subscribed = ()

    def connect(self):
        self.connected = True

    def subscribe(self, symbols):
        self.subscribed = tuple(symbols)

    def events(self):
        if not self.connected:
            raise RuntimeError("feed is not connected")
        yield from self._events

    def disconnect(self):
        self.connected = False


def make_event(
    *,
    event_id: str,
    timestamp: datetime,
    price: float,
    volume: float = 10.0,
) -> MarketEvent:
    return MarketEvent(
        event_id=event_id,
        symbol="RELIANCE",
        exchange="NSE",
        event_type=MarketEventType.TRADE,
        price=price,
        volume=volume,
        exchange_timestamp=timestamp,
        received_timestamp=timestamp,
    )


def test_realtime_pipeline_module_exists():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    assert RealtimeMarketDataPipeline is not None


def test_pipeline_requires_feed():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    with pytest.raises(TypeError):
        RealtimeMarketDataPipeline(
            feed=None,
            validator=MarketEventValidator(),
            aggregator=CandleAggregator(),
        )


def test_pipeline_requires_validator():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    feed = StubMarketFeed(())

    with pytest.raises(TypeError):
        RealtimeMarketDataPipeline(
            feed=feed,
            validator=None,
            aggregator=CandleAggregator(),
        )


def test_pipeline_requires_aggregator():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    feed = StubMarketFeed(())

    with pytest.raises(TypeError):
        RealtimeMarketDataPipeline(
            feed=feed,
            validator=MarketEventValidator(),
            aggregator=None,
        )


def test_pipeline_connects_and_subscribes():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    feed = StubMarketFeed(())

    pipeline = RealtimeMarketDataPipeline(
        feed=feed,
        validator=MarketEventValidator(),
        aggregator=CandleAggregator(),
    )

    pipeline.start(("RELIANCE", "HDFCBANK"))

    assert feed.connected is True
    assert feed.subscribed == ("RELIANCE", "HDFCBANK")

    pipeline.stop()

    assert feed.connected is False


def test_pipeline_validates_events_before_candle_aggregation():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    base = datetime(
        2026,
        9,
        4,
        9,
        15,
        tzinfo=timezone.utc,
    )

    events = (
        make_event(
            event_id="event-1",
            timestamp=base,
            price=100.0,
        ),
        make_event(
            event_id="event-2",
            timestamp=base.replace(minute=20),
            price=105.0,
        ),
    )

    feed = StubMarketFeed(events)

    validator = MarketEventValidator(
        max_event_age_seconds=3600,
    )

    pipeline = RealtimeMarketDataPipeline(
        feed=feed,
        validator=validator,
        aggregator=CandleAggregator(),
    )

    pipeline.start(("RELIANCE",))

    candles = list(pipeline.run(now=base.replace(minute=25)))

    assert len(candles) == 1
    assert candles[0].open == 100.0
    assert candles[0].close == 100.0

    pipeline.stop()


def test_pipeline_does_not_send_invalid_events_to_aggregator():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    base = datetime(
        2026,
        9,
        4,
        9,
        15,
        tzinfo=timezone.utc,
    )

    events = (
        make_event(
            event_id="duplicate",
            timestamp=base,
            price=100.0,
        ),
        make_event(
            event_id="duplicate",
            timestamp=base,
            price=999.0,
        ),
    )

    feed = StubMarketFeed(events)

    validator = MarketEventValidator(
        max_event_age_seconds=3600,
    )

    pipeline = RealtimeMarketDataPipeline(
        feed=feed,
        validator=validator,
        aggregator=CandleAggregator(),
    )

    pipeline.start(("RELIANCE",))

    candles = list(pipeline.run(now=base.replace(minute=20)))

    assert candles == []

    flushed = pipeline.flush()

    assert len(flushed) == 1
    assert flushed[0].open == 100.0
    assert flushed[0].close == 100.0

    pipeline.stop()


def test_pipeline_records_validation_metrics():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    base = datetime(
        2026,
        9,
        4,
        9,
        15,
        tzinfo=timezone.utc,
    )

    events = (
        make_event(
            event_id="event-1",
            timestamp=base,
            price=100.0,
        ),
        make_event(
            event_id="event-1",
            timestamp=base,
            price=101.0,
        ),
    )

    metrics = DataQualityMetrics()

    feed = StubMarketFeed(events)

    pipeline = RealtimeMarketDataPipeline(
        feed=feed,
        validator=MarketEventValidator(
            max_event_age_seconds=3600,
        ),
        aggregator=CandleAggregator(),
        metrics=metrics,
    )

    pipeline.start(("RELIANCE",))

    list(pipeline.run(now=base.replace(minute=20)))

    snapshot = metrics.snapshot()

    assert snapshot.events_received == 2
    assert snapshot.events_accepted == 1
    assert snapshot.events_rejected == 1
    assert snapshot.duplicate_events == 1

    pipeline.stop()


def test_pipeline_flushes_current_candles():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    timestamp = datetime(
        2026,
        9,
        4,
        9,
        15,
        tzinfo=timezone.utc,
    )

    feed = StubMarketFeed(
        (
            make_event(
                event_id="event-1",
                timestamp=timestamp,
                price=100.0,
            ),
        )
    )

    pipeline = RealtimeMarketDataPipeline(
        feed=feed,
        validator=MarketEventValidator(
            max_event_age_seconds=3600,
        ),
        aggregator=CandleAggregator(),
    )

    pipeline.start(("RELIANCE",))

    assert list(pipeline.run(now=timestamp.replace(minute=20))) == []

    flushed = pipeline.flush()

    assert len(flushed) == 1
    assert flushed[0].symbol == "RELIANCE"

    pipeline.stop()


def test_pipeline_rejects_double_start():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    feed = StubMarketFeed(())

    pipeline = RealtimeMarketDataPipeline(
        feed=feed,
        validator=MarketEventValidator(),
        aggregator=CandleAggregator(),
    )

    pipeline.start(("RELIANCE",))

    with pytest.raises(RuntimeError, match="already started"):
        pipeline.start(("RELIANCE",))

    pipeline.stop()


def test_pipeline_stop_is_idempotent():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    feed = StubMarketFeed(())

    pipeline = RealtimeMarketDataPipeline(
        feed=feed,
        validator=MarketEventValidator(),
        aggregator=CandleAggregator(),
    )

    pipeline.stop()

    pipeline.start(("RELIANCE",))
    pipeline.stop()
    pipeline.stop()

    assert feed.connected is False


def test_pipeline_reset_clears_validation_and_candle_state():
    from market.data.realtime_pipeline import RealtimeMarketDataPipeline

    timestamp = datetime(
        2026,
        9,
        4,
        9,
        15,
        tzinfo=timezone.utc,
    )

    event = make_event(
        event_id="reset-event",
        timestamp=timestamp,
        price=100.0,
    )

    metrics = DataQualityMetrics()

    feed = StubMarketFeed((event,))

    pipeline = RealtimeMarketDataPipeline(
        feed=feed,
        validator=MarketEventValidator(
            max_event_age_seconds=3600,
        ),
        aggregator=CandleAggregator(),
        metrics=metrics,
    )

    pipeline.start(("RELIANCE",))

    list(pipeline.run(now=timestamp.replace(minute=20)))

    assert metrics.snapshot().events_accepted == 1
    assert len(pipeline.flush()) == 1

    # The event ID was previously accepted.
    pipeline.validator.validate(event, now=timestamp.replace(minute=20))

    pipeline.reset()

    # Reset clears duplicate detection, active candles and metrics.
    assert metrics.snapshot().events_received == 0
    assert metrics.snapshot().events_accepted == 0
    assert pipeline.flush() == []

    pipeline.stop()
