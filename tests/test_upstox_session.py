"""Tests for the Upstox market-data authorization/session boundary."""

from market.data.ingestion.providers.upstox.session import UpstoxMarketDataSession


def test_authorize_builds_market_data_session(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "sandbox-token")
    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.session.get_authorized_websocket_uri",
        lambda token, timeout_seconds: "wss://sandbox.example/feed",
    )

    session = UpstoxMarketDataSession.authorize()

    assert session.websocket_uri == "wss://sandbox.example/feed"
    assert session.config.environment == "SANDBOX"
    assert session.evidence()["market_data_only"] is True
    assert session.evidence()["live_broker_order_submission"] is False


def test_authorization_does_not_expose_token(monkeypatch):
    secret = "super-secret-token"
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", secret)
    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.session.get_authorized_websocket_uri",
        lambda token, timeout_seconds: "wss://sandbox.example/feed",
    )

    session = UpstoxMarketDataSession.authorize()

    assert secret not in str(session.evidence())
    assert secret not in str(session)


def test_authorization_error_propagates(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "sandbox-token")

    def fail(*args, **kwargs):
        raise RuntimeError("authorization failed")

    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.session.get_authorized_websocket_uri",
        fail,
    )

    try:
        UpstoxMarketDataSession.authorize()
    except RuntimeError as exc:
        assert str(exc) == "authorization failed"
    else:
        raise AssertionError("authorization failure must propagate")
