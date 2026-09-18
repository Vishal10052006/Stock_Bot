from datetime import datetime, timezone

import pytest

from market.data.historical.adapters.nse_security import (
    NSESecurityDataError,
    NSESecurityWiseAdapter,
)
from market.data.historical.models import HistoricalDataRequest


def raw_record(date_text="03-Sep-2026"):
    return {
        "CH_SYMBOL": "RELIANCE",
        "CH_SERIES": "EQ",
        "mTIMESTAMP": date_text,
        "CH_PREVIOUS_CLS_PRICE": 1313.1,
        "CH_OPENING_PRICE": 1313.1,
        "CH_TRADE_HIGH_PRICE": 1316.8,
        "CH_TRADE_LOW_PRICE": 1302.5,
        "CH_LAST_TRADED_PRICE": 1302.5,
        "CH_CLOSING_PRICE": 1302.5,
        "VWAP": 1308.7,
        "CH_TOT_TRADED_QTY": 9721454,
        "CH_TOT_TRADED_VAL": 12722456176.5,
        "CH_TOTAL_TRADES": 158231,
    }


def make_request(
    *,
    start_hour=0,
    end_hour=0,
):
    return HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(
            2026,
            9,
            3,
            start_hour,
            tzinfo=timezone.utc,
        ),
        end=datetime(
            2026,
            9,
            3,
            end_hour,
            tzinfo=timezone.utc,
        ),
    )


def test_parse_real_nse_record():
    adapter = NSESecurityWiseAdapter()

    bar = adapter._parse_record(raw_record())

    assert bar.symbol == "RELIANCE"
    assert bar.series == "EQ"
    assert bar.session_date.isoformat() == "2026-09-03"
    assert bar.open == 1313.1
    assert bar.high == 1316.8
    assert bar.low == 1302.5
    assert bar.close == 1302.5
    assert bar.vwap == 1308.7
    assert bar.traded_quantity == 9721454
    assert bar.traded_value == 12722456176.5
    assert bar.total_trades == 158231


def test_parser_rejects_missing_field():
    adapter = NSESecurityWiseAdapter()

    record = raw_record()
    del record["VWAP"]

    with pytest.raises(ValueError, match="missing fields"):
        adapter._parse_record(record)


def test_parser_rejects_non_mapping_record():
    adapter = NSESecurityWiseAdapter()

    with pytest.raises(ValueError, match="must be an object"):
        adapter._parse_record(["invalid"])


def test_parser_rejects_invalid_date():
    adapter = NSESecurityWiseAdapter()

    with pytest.raises(ValueError, match="invalid NSE"):
        adapter._parse_record(raw_record("not-a-date"))


def test_request_requires_explicit_dates():
    adapter = NSESecurityWiseAdapter()

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
    )

    with pytest.raises(ValueError, match="require start and end"):
        adapter.get_daily_bars(request)


def test_request_rejects_non_nse_exchange():
    adapter = NSESecurityWiseAdapter()

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="BSE",
        timeframe_minutes=5,
        start=datetime(2026, 9, 3, tzinfo=timezone.utc),
        end=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="only supports NSE"):
        adapter.get_daily_bars(request)


def test_request_rejects_non_five_minute_contract():
    adapter = NSESecurityWiseAdapter()

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=1,
        start=datetime(2026, 9, 3, tzinfo=timezone.utc),
        end=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="does not provide"):
        adapter.get_daily_bars(request)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def test_api_mapping_uses_inclusive_nse_to_date():
    session = FakeSession(
        {
            "data": [
                raw_record("03-Sep-2026"),
                raw_record("02-Sep-2026"),
            ]
        }
    )

    adapter = NSESecurityWiseAdapter(session=session)

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(
            2026,
            9,
            2,
            tzinfo=timezone.utc,
        ),
        end=datetime(
            2026,
            9,
            4,
            tzinfo=timezone.utc,
        ),
    )

    bars = adapter.get_daily_bars(request)

    assert {bar.session_date.isoformat() for bar in bars} == {
        "2026-09-02",
        "2026-09-03",
    }

    api_url, kwargs = session.calls[1]

    assert api_url.endswith(
        "/api/historicalOR/generateSecurityWiseHistoricalData"
    )

    assert kwargs["params"] == {
        "from": "02-09-2026",
        "to": "03-09-2026",
        "symbol": "RELIANCE",
        "type": "priceVolume",
        "series": "EQ",
    }


def test_adapter_excludes_stock_bot_end_boundary():
    session = FakeSession(
        {
            "data": [
                raw_record("02-Sep-2026"),
                raw_record("03-Sep-2026"),
                raw_record("04-Sep-2026"),
            ]
        }
    )

    adapter = NSESecurityWiseAdapter(session=session)

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(2026, 9, 2, tzinfo=timezone.utc),
        end=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )

    bars = adapter.get_daily_bars(request)

    assert tuple(
        bar.session_date.isoformat()
        for bar in bars
    ) == (
        "2026-09-02",
        "2026-09-03",
    )


def test_session_establishment_occurs_before_api_request():
    session = FakeSession({"data": []})
    adapter = NSESecurityWiseAdapter(session=session)

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(2026, 9, 3, tzinfo=timezone.utc),
        end=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )

    adapter.get_daily_bars(request)

    assert len(session.calls) == 2

    assert session.calls[0][0].endswith(
        "/report-detail/eq_security"
    )

    assert session.calls[1][0].endswith(
        "/api/historicalOR/generateSecurityWiseHistoricalData"
    )


class ErrorResponse:
    def raise_for_status(self):
        raise RuntimeError("NSE HTTP failure")

    def json(self):
        raise AssertionError("json() must not be called")


class InvalidJsonResponse:
    def raise_for_status(self):
        return None

    def json(self):
        raise ValueError("invalid JSON")


class InvalidPayloadSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return FakeResponse({"data": []})
        return InvalidJsonResponse()


class HttpFailureSession:
    def __init__(self):
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return FakeResponse({"data": []})
        return ErrorResponse()


def test_http_failure_is_not_silently_accepted():
    session = HttpFailureSession()
    adapter = NSESecurityWiseAdapter(session=session)

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(2026, 9, 3, tzinfo=timezone.utc),
        end=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )

    with pytest.raises(
        NSESecurityDataError,
        match="historical request failed",
    ):
        adapter.get_daily_bars(request)


def test_invalid_json_is_not_silently_accepted():
    session = InvalidPayloadSession()
    adapter = NSESecurityWiseAdapter(session=session)

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(2026, 9, 3, tzinfo=timezone.utc),
        end=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )

    with pytest.raises(
        NSESecurityDataError,
        match="invalid JSON",
    ):
        adapter.get_daily_bars(request)


class SessionEstablishmentFailureSession:
    def get(self, url, **kwargs):
        raise RuntimeError("NSE session establishment failure")


def test_session_establishment_failure_uses_adapter_error():
    session = SessionEstablishmentFailureSession()
    adapter = NSESecurityWiseAdapter(session=session)

    request = HistoricalDataRequest(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        start=datetime(2026, 9, 3, tzinfo=timezone.utc),
        end=datetime(2026, 9, 4, tzinfo=timezone.utc),
    )

    with pytest.raises(
        NSESecurityDataError,
        match="session establishment failed",
    ):
        adapter.get_daily_bars(request)
