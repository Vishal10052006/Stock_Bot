"""Tests for the Upstox V3 historical-data adapter."""

from datetime import datetime, timezone

import pytest

from market.data.historical.adapters.upstox import (
    UpstoxHistoricalDataError,
    UpstoxHistoricalMarketDataProvider,
)
from market.data.historical.models import HistoricalDataRequest
from market.data.ingestion.providers.upstox.instrument_mapper import (
    UpstoxInstrumentMapper,
)


class FakeResponse:
    """Minimal HTTP response double."""

    def __init__(self, payload, *, status_code=200):
        self._payload = payload
        self.status_code = status_code

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def json(self):
        return self._payload


class FakeSession:
    """Minimal HTTP session double."""

    def __init__(self, response):
        self.response = response
        self.url = None
        self.headers = None
        self.timeout = None

    def get(self, url, *, headers, timeout):
        self.url = url
        self.headers = headers
        self.timeout = timeout
        return self.response


def make_provider(response):
    """Build a provider using a deterministic HTTP double."""
    if not isinstance(response, FakeResponse):
        response = FakeResponse(response)

    session = FakeSession(response)

    mapper = UpstoxInstrumentMapper(
        {"RELIANCE": "NSE_EQ|INE002A01018"}
    )

    provider = UpstoxHistoricalMarketDataProvider(
        "test-access-token",
        mapper,
        session=session,
        base_url="https://example.test/v3/historical-candle",
    )

    return provider, session


def make_request():
    """Create a deterministic five-minute historical request."""
    return HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(
            2026,
            9,
            1,
            9,
            15,
            tzinfo=timezone.utc,
        ),
        end=datetime(
            2026,
            9,
            1,
            15,
            30,
            tzinfo=timezone.utc,
        ),
    )


def valid_payload():
    """Return a minimal valid Upstox historical response."""
    return {
        "status": "success",
        "data": {
            "candles": [
                [
                    "2026-09-01T09:15:00+00:00",
                    100.0,
                    101.0,
                    99.0,
                    100.5,
                    10000,
                    0,
                ],
                [
                    "2026-09-01T09:20:00+00:00",
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


def test_provider_has_authoritative_role():
    provider, _ = make_provider(valid_payload())

    from market.data.historical.providers import HistoricalProviderRole

    assert provider.role is HistoricalProviderRole.CANONICAL


def test_provider_converts_upstox_candles_to_canonical_candles():
    provider, _ = make_provider(valid_payload())

    bars = provider.get_bars(make_request())

    assert len(bars) == 2

    assert bars[0].symbol == "RELIANCE"
    assert bars[0].exchange == "NSE"
    assert bars[0].timeframe_minutes == 5

    assert bars[0].open == 100.0
    assert bars[0].high == 101.0
    assert bars[0].low == 99.0
    assert bars[0].close == 100.5
    assert bars[0].volume == 10000.0

    assert bars[0].timestamp == datetime(
        2026,
        9,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )


def test_provider_builds_correct_historical_url_and_headers():
    provider, session = make_provider(valid_payload())

    provider.get_bars(make_request())

    assert (
        session.url
        == "https://example.test/v3/historical-candle/"
        "NSE_EQ%7CINE002A01018/minutes/5/2026-09-01/2026-09-01"
    )

    assert session.headers["Authorization"] == (
        "Bearer test-access-token"
    )
    assert session.headers["Accept"] == "application/json"
    assert session.timeout == 10.0


def test_provider_rejects_missing_start():
    mapper = UpstoxInstrumentMapper(
        {"RELIANCE": "NSE_EQ|INE002A01018"}
    )

    provider = UpstoxHistoricalMarketDataProvider(
        "token",
        mapper,
        session=FakeSession(valid_payload()),
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    with pytest.raises(
        ValueError,
        match="require start and end",
    ):
        provider.get_bars(request)


def test_provider_rejects_missing_end():
    mapper = UpstoxInstrumentMapper(
        {"RELIANCE": "NSE_EQ|INE002A01018"}
    )

    provider = UpstoxHistoricalMarketDataProvider(
        "token",
        mapper,
        session=FakeSession(valid_payload()),
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
    )

    with pytest.raises(
        ValueError,
        match="require an end timestamp",
    ):
        provider.get_bars(request)


def test_provider_rejects_non_nse_request():
    mapper = UpstoxInstrumentMapper(
        {"RELIANCE": "NSE_EQ|INE002A01018"}
    )

    provider = UpstoxHistoricalMarketDataProvider(
        "token",
        mapper,
        session=FakeSession(valid_payload()),
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="BSE",
        timeframe_minutes=5,
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="supports NSE only"):
        provider.get_bars(request)


def test_provider_rejects_interval_above_upstox_minute_limit():
    mapper = UpstoxInstrumentMapper(
        {"RELIANCE": "NSE_EQ|INE002A01018"}
    )

    provider = UpstoxHistoricalMarketDataProvider(
        "token",
        mapper,
        session=FakeSession(valid_payload()),
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=301,
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="<= 300"):
        provider.get_bars(request)


def test_provider_rejects_http_error():
    provider, _ = make_provider(
        {"status": "error"},
    )

    provider._session.response = FakeResponse(
        {"status": "error"},
        status_code=401,
    )

    with pytest.raises(
        UpstoxHistoricalDataError,
        match="HTTP 401",
    ):
        provider.get_bars(make_request())


def test_provider_rejects_invalid_json_response(monkeypatch):
    provider, session = make_provider(valid_payload())

    class InvalidJsonResponse(FakeResponse):
        def json(self):
            raise ValueError("invalid json")

    session.response = InvalidJsonResponse({})

    with pytest.raises(
        UpstoxHistoricalDataError,
        match="valid JSON",
    ):
        provider.get_bars(make_request())


def test_provider_rejects_unsuccessful_payload():
    provider, session = make_provider(
        {"status": "error", "data": {}}
    )

    session.response = FakeResponse(
        {"status": "error", "data": {}}
    )

    with pytest.raises(
        UpstoxHistoricalDataError,
        match="did not report success",
    ):
        provider.get_bars(make_request())


def test_provider_rejects_missing_candles():
    provider, session = make_provider(
        {"status": "success", "data": {}}
    )

    session.response = FakeResponse(
        {"status": "success", "data": {}}
    )

    with pytest.raises(
        UpstoxHistoricalDataError,
        match="did not contain candles",
    ):
        provider.get_bars(make_request())


def test_provider_rejects_empty_candles():
    provider, session = make_provider(
        {"status": "success", "data": {"candles": []}}
    )

    session.response = FakeResponse(
        {"status": "success", "data": {"candles": []}}
    )

    with pytest.raises(
        UpstoxHistoricalDataError,
        match="no historical candles",
    ):
        provider.get_bars(make_request())


def test_provider_rejects_malformed_candle():
    provider, session = make_provider(
        {
            "status": "success",
            "data": {"candles": [["bad"]]},
        }
    )

    session.response = FakeResponse(
        {
            "status": "success",
            "data": {"candles": [["bad"]]},
        }
    )

    with pytest.raises(
        UpstoxHistoricalDataError,
        match="malformed candle",
    ):
        provider.get_bars(make_request())


def test_provider_rejects_naive_timestamp():
    provider, session = make_provider(
        {
            "status": "success",
            "data": {
                "candles": [
                    [
                        "2026-09-01T09:15:00",
                        100,
                        101,
                        99,
                        100,
                        1000,
                        0,
                    ]
                ]
            },
        }
    )

    session.response = FakeResponse(
        {
            "status": "success",
            "data": {
                "candles": [
                    [
                        "2026-09-01T09:15:00",
                        100,
                        101,
                        99,
                        100,
                        1000,
                        0,
                    ]
                ]
            },
        }
    )

    with pytest.raises(
        UpstoxHistoricalDataError,
        match="timezone-naive",
    ):
        provider.get_bars(make_request())


def test_provider_rejects_non_finite_ohlcv():
    provider, session = make_provider(
        {
            "status": "success",
            "data": {
                "candles": [
                    [
                        "2026-09-01T09:15:00+00:00",
                        "nan",
                        101,
                        99,
                        100,
                        1000,
                        0,
                    ]
                ]
            },
        }
    )

    session.response = FakeResponse(
        {
            "status": "success",
            "data": {
                "candles": [
                    [
                        "2026-09-01T09:15:00+00:00",
                        "nan",
                        101,
                        99,
                        100,
                        1000,
                        0,
                    ]
                ]
            },
        }
    )

    with pytest.raises(
        UpstoxHistoricalDataError,
        match="non-finite",
    ):
        provider.get_bars(make_request())


def test_provider_rejects_negative_volume():
    provider, session = make_provider(
        {
            "status": "success",
            "data": {
                "candles": [
                    [
                        "2026-09-01T09:15:00+00:00",
                        100,
                        101,
                        99,
                        100,
                        -1,
                        0,
                    ]
                ]
            },
        }
    )

    session.response = FakeResponse(
        {
            "status": "success",
            "data": {
                "candles": [
                    [
                        "2026-09-01T09:15:00+00:00",
                        100,
                        101,
                        99,
                        100,
                        -1,
                        0,
                    ]
                ]
            },
        }
    )

    with pytest.raises(
        UpstoxHistoricalDataError,
        match="negative volume",
    ):
        provider.get_bars(make_request())


def test_provider_does_not_repair_or_invent_candles():
    payload = {
        "status": "success",
        "data": {
            "candles": [
                [
                    "2026-09-01T09:15:00+00:00",
                    100,
                    101,
                    99,
                    100,
                    1000,
                    0,
                ],
                [
                    "2026-09-01T09:25:00+00:00",
                    100,
                    101,
                    99,
                    100,
                    1000,
                    0,
                ],
            ]
        },
    }

    provider, _ = make_provider(payload)

    bars = provider.get_bars(make_request())

    assert len(bars) == 2
    assert bars[1].timestamp.minute == 25


def test_provider_chunks_historical_requests_into_max_30_day_windows():
    """Long historical requests must be split into bounded date windows."""
    from datetime import timedelta

    provider, _ = make_provider(valid_payload())

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(
            2026,
            1,
            1,
            9,
            15,
            tzinfo=timezone.utc,
        ),
        end=datetime(
            2026,
            3,
            15,
            15,
            30,
            tzinfo=timezone.utc,
        ),
    )

    chunks = list(provider._iter_date_chunks(request))

    assert len(chunks) == 3

    assert chunks[0] == (
        datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc),
        datetime(2026, 1, 30, 23, 59, 59, tzinfo=timezone.utc),
    )

    assert chunks[1] == (
        datetime(2026, 1, 31, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 3, 1, 23, 59, 59, tzinfo=timezone.utc),
    )

    assert chunks[2] == (
        datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc),
        request.end,
    )


def test_provider_fetches_each_long_request_chunk_and_merges_bars():
    """Long Upstox requests must fetch every chunk and merge chronologically."""
    from datetime import datetime, timezone

    class MultiChunkSession:
        def __init__(self):
            self.calls = []

        def get(self, url, *, headers, timeout):
            self.calls.append(
                {
                    "url": url,
                    "headers": headers,
                    "timeout": timeout,
                }
            )

            if len(self.calls) == 1:
                payload = {
                    "status": "success",
                    "data": {
                        "candles": [
                            [
                                "2026-01-01T09:15:00+00:00",
                                100,
                                101,
                                99,
                                100,
                                1000,
                                0,
                            ]
                        ]
                    },
                }
            elif len(self.calls) == 2:
                payload = {
                    "status": "success",
                    "data": {
                        "candles": [
                            [
                                "2026-02-01T09:15:00+00:00",
                                101,
                                102,
                                100,
                                101,
                                1100,
                                0,
                            ]
                        ]
                    },
                }
            else:
                payload = {
                    "status": "success",
                    "data": {
                        "candles": [
                            [
                                "2026-03-01T09:15:00+00:00",
                                102,
                                103,
                                101,
                                102,
                                1200,
                                0,
                            ]
                        ]
                    },
                }

            return FakeResponse(payload)

    session = MultiChunkSession()

    provider = UpstoxHistoricalMarketDataProvider(
        "token",
        UpstoxInstrumentMapper(
            {"RELIANCE": "NSE_EQ|INE002A01018"}
        ),
        session=session,
        base_url="https://example.test/v3/historical-candle",
    )

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(
            2026,
            1,
            1,
            9,
            15,
            tzinfo=timezone.utc,
        ),
        end=datetime(
            2026,
            3,
            15,
            15,
            30,
            tzinfo=timezone.utc,
        ),
    )

    bars = provider.get_bars(request)

    assert len(session.calls) == 3
    assert len(bars) == 3

    assert "2026-01-30/2026-01-01" in session.calls[0]["url"]
    assert "2026-03-01/2026-01-31" in session.calls[1]["url"]
    assert "2026-03-15/2026-03-02" in session.calls[2]["url"]

    timestamps = [bar.timestamp for bar in bars]

    assert timestamps == sorted(timestamps)
    assert len(timestamps) == len(set(timestamps))
    assert [bar.close for bar in bars] == [100.0, 101.0, 102.0]


def test_provider_filters_bars_to_exact_requested_time_window():
    """Provider must enforce the request's [start, end) time boundary."""
    payload = {
        "status": "success",
        "data": {
            "candles": [
                [
                    "2026-09-01T09:15:00+00:00",
                    99,
                    100,
                    98,
                    99,
                    1000,
                    0,
                ],
                [
                    "2026-09-01T10:00:00+00:00",
                    100,
                    101,
                    99,
                    100,
                    1000,
                    0,
                ],
                [
                    "2026-09-01T10:55:00+00:00",
                    101,
                    102,
                    100,
                    101,
                    1000,
                    0,
                ],
                [
                    "2026-09-01T11:00:00+00:00",
                    102,
                    103,
                    101,
                    102,
                    1000,
                    0,
                ],
                [
                    "2026-09-01T15:25:00+00:00",
                    103,
                    104,
                    102,
                    103,
                    1000,
                    0,
                ],
            ],
        },
    }

    provider, _ = make_provider(payload)

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(
            2026,
            9,
            1,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        end=datetime(
            2026,
            9,
            1,
            11,
            0,
            tzinfo=timezone.utc,
        ),
    )

    bars = provider.get_bars(request)

    timestamps = [bar.timestamp for bar in bars]

    assert timestamps == [
        datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 10, 55, tzinfo=timezone.utc),
    ]

    assert all(
        request.start <= timestamp < request.end
        for timestamp in timestamps
    )
