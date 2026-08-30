"""Unit tests for the Upstox V3 authorization boundary."""

import json

import pytest

from market.data.ingestion.providers.upstox.auth import (
    UpstoxAuthorizationError,
    get_authorized_websocket_uri,
)


class FakeResponse:
    """Minimal context-manager response for HTTP tests."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(
            {
                "status": "success",
                "data": {"authorized_redirect_uri": "wss://example.test/feed"},
            }
        ).encode("utf-8")


class FakeUrlopen:
    """Callable replacement for urllib.request.urlopen."""

    def __init__(self, response):
        self.response = response
        self.request = None

    def __call__(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return self.response


def test_authorization_returns_websocket_uri(monkeypatch):
    """A successful authorization response should expose the V3 socket URI."""
    fake = FakeUrlopen(FakeResponse())
    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.auth.urlopen",
        fake,
    )

    uri = get_authorized_websocket_uri("access-token")

    assert uri == "wss://example.test/feed"
    assert fake.request.get_header("Authorization") == "Bearer access-token"
    assert fake.request.get_header("Accept") == "application/json"


def test_authorization_rejects_empty_token():
    """An empty token should fail before any network request."""
    with pytest.raises(ValueError, match="access_token"):
        get_authorized_websocket_uri("  ")


def test_authorization_rejects_malformed_response(monkeypatch):
    """Missing authorization data must become a typed provider error."""
    class MalformedResponse(FakeResponse):
        def read(self):
            return b'{"status":"success","data":{}}'

    fake = FakeUrlopen(MalformedResponse())
    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.auth.urlopen",
        fake,
    )

    with pytest.raises(UpstoxAuthorizationError):
        get_authorized_websocket_uri("access-token")
