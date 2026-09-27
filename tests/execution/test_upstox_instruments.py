from __future__ import annotations

import json

import pytest

import execution.adapters.upstox_instrument_search as search_module
from execution.adapters.upstox_instruments import (
    InstrumentResolutionError,
    UpstoxInstrumentResolver,
)
from execution.adapters.upstox_instrument_search import UpstoxInstrumentSearchClient


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_resolver_uses_exact_symbol_and_caches_result():
    class FakeClient:
        def __init__(self):
            self.calls = 0

        def search_instruments(self, query, *, exchange, segment, limit):
            self.calls += 1
            return [
                {
                    "instrument_key": "NSE_EQ|INE123",
                    "trading_symbol": query,
                    "exchange": exchange,
                    "segment": segment,
                }
            ]

    client = FakeClient()
    resolver = UpstoxInstrumentResolver(client)

    first = resolver.resolve("itc")
    second = resolver.resolve("ITC")

    assert first.instrument_key == "NSE_EQ|INE123"
    assert second == first
    assert client.calls == 1


def test_resolver_rejects_no_exact_match():
    class FakeClient:
        def search_instruments(self, query, *, exchange, segment, limit):
            return [{"instrument_key": "NSE_EQ|INE123", "trading_symbol": "ITCBEES"}]

    with pytest.raises(InstrumentResolutionError, match="no exact"):
        UpstoxInstrumentResolver(FakeClient()).resolve("ITC")


def test_resolver_rejects_ambiguous_exact_matches():
    class FakeClient:
        def search_instruments(self, query, *, exchange, segment, limit):
            return [
                {
                    "instrument_key": "NSE_EQ|INE123",
                    "trading_symbol": "ITC",
                    "exchange": "NSE",
                    "segment": "EQ",
                },
                {
                    "instrument_key": "NSE_EQ|INE456",
                    "trading_symbol": "ITC",
                    "exchange": "NSE",
                    "segment": "EQ",
                },
            ]

    with pytest.raises(InstrumentResolutionError, match="ambiguous"):
        UpstoxInstrumentResolver(FakeClient()).resolve("ITC")


def test_resolver_rejects_wrong_exchange_or_segment():
    class FakeClient:
        def search_instruments(self, query, *, exchange, segment, limit):
            return [
                {
                    "instrument_key": "NSE_EQ|INE123",
                    "trading_symbol": "ITC",
                    "exchange": "BSE",
                    "segment": "EQ",
                }
            ]

    with pytest.raises(InstrumentResolutionError, match="exchange"):
        UpstoxInstrumentResolver(FakeClient()).resolve("ITC")


def test_search_client_builds_read_only_request(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.method
        seen["authorization"] = request.get_header("Authorization")
        return FakeResponse(
            {
                "status": "success",
                "data": [
                    {
                        "instrument_key": "NSE_EQ|INE123",
                        "trading_symbol": "ITC",
                        "exchange": "NSE",
                        "segment": "EQ",
                    }
                ],
            }
        )

    monkeypatch.setattr(search_module, "urlopen", fake_urlopen)

    client = UpstoxInstrumentSearchClient("sandbox-token")
    records = client.search_instruments("ITC")

    assert records[0]["instrument_key"] == "NSE_EQ|INE123"
    assert "query=ITC" in seen["url"]
    assert "exchanges=NSE" in seen["url"]
    assert "segments=EQ" in seen["url"]
    assert seen["method"] == "GET"
    assert seen["authorization"] == "Bearer sandbox-token"
