"""Unit tests for the Upstox V3 authorization boundary."""

import pytest

from market.data.ingestion.providers.upstox.auth import (
    UpstoxAuthorizationError,
    get_authorized_websocket_uri,
)


class FakeResponse:
    """Minimal response double compatible with ``requests``."""

    def __init__(self, payload, *, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = "fake-response"

    @property
    def ok(self):
        """Mirror ``requests.Response.ok`` for the production boundary."""
        return 200 <= self.status_code < 400

    def json(self):
        """Return the JSON payload supplied by the test."""
        return self._payload


class FakeRequests:
    """Minimal ``requests`` module double for authorization tests."""

    RequestException = RuntimeError

    def __init__(self, response):
        self.response = response
        self.url = None
        self.headers = None
        self.timeout = None

    def get(self, url, *, headers, timeout):
        """Capture the request and return the configured fake response."""
        self.url = url
        self.headers = headers
        self.timeout = timeout
        return self.response


def test_authorization_returns_websocket_uri(monkeypatch):
    """A successful authorization response should expose the V3 socket URI."""
    fake_response = FakeResponse(
        {
            "status": "success",
            "data": {"authorized_redirect_uri": "wss://example.test/feed"},
        }
    )
    fake_requests = FakeRequests(fake_response)
    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.auth.requests",
        fake_requests,
    )

    uri = get_authorized_websocket_uri("access-token")

    assert uri == "wss://example.test/feed"
    assert fake_requests.url.endswith("/v3/feed/market-data-feed/authorize")
    assert fake_requests.headers["Authorization"] == "Bearer access-token"
    assert fake_requests.headers["Accept"] == "application/json"
    assert fake_requests.headers["User-Agent"] == "Stock-Bot/1.0"
    assert fake_requests.timeout == 10.0


def test_authorization_rejects_empty_token():
    """An empty token should fail before any network request."""
    with pytest.raises(ValueError, match="access_token"):
        get_authorized_websocket_uri("  ")


def test_authorization_rejects_malformed_response(monkeypatch):
    """Missing authorization data must become a typed provider error."""
    fake_response = FakeResponse({"status": "success", "data": {}})
    fake_requests = FakeRequests(fake_response)
    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.auth.requests",
        fake_requests,
    )

    with pytest.raises(
        UpstoxAuthorizationError,
        match="authorized redirect URI",
    ):
        get_authorized_websocket_uri("access-token")


def test_authorization_rejects_http_error(monkeypatch):
    """Non-success HTTP responses must become typed provider errors."""
    fake_response = FakeResponse(
        {"status": "error"},
        status_code=403,
    )
    fake_requests = FakeRequests(fake_response)
    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.auth.requests",
        fake_requests,
    )

    with pytest.raises(
        UpstoxAuthorizationError,
        match="HTTP 403",
    ):
        get_authorized_websocket_uri("access-token")
