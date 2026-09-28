"""Unit tests for the Upstox provider configuration boundary."""

import pytest

from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig


def test_config_reads_sandbox_access_token(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "token-value")
    config = UpstoxFeedConfig.from_env()
    assert config.access_token == "token-value"
    assert config.environment == "SANDBOX"
    assert config.live_order_submission is False
    assert config.mode == "ltpc"
    assert config.timeout_seconds == 10.0


def test_config_requires_access_token(monkeypatch):
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    with pytest.raises(ValueError, match="UPSTOX_ACCESS_TOKEN"):
        UpstoxFeedConfig.from_env()


def test_config_defaults_to_sandbox(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "token-value")
    monkeypatch.delenv("STOCK_BOT_UPSTOX_MODE", raising=False)
    config = UpstoxFeedConfig.from_env()
    assert config.environment == "SANDBOX"
    assert config.live_order_submission is False


def test_config_rejects_live_environment(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "token-value")
    monkeypatch.setenv("STOCK_BOT_UPSTOX_MODE", "LIVE")
    with pytest.raises(ValueError, match="must be SANDBOX"):
        UpstoxFeedConfig.from_env()


def test_config_rejects_live_order_submission(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "token-value")
    monkeypatch.setenv("STOCK_BOT_LIVE_ORDER_SUBMISSION", "true")
    with pytest.raises(ValueError, match="must remain false"):
        UpstoxFeedConfig.from_env()


def test_evidence_never_contains_secret(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "super-secret-token")
    monkeypatch.setenv("UPSTOX_CLIENT_ID", "sandbox-client")
    config = UpstoxFeedConfig.from_env()
    evidence = config.evidence()
    assert evidence["access_token_configured"] is True
    assert "super-secret-token" not in str(evidence)
    assert evidence["client_id_configured"] is True
    assert evidence["live_order_submission"] is False
    assert evidence["live_broker_order_submission"] is False


def test_fingerprint_is_deterministic(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "token-a")
    first = UpstoxFeedConfig.from_env().fingerprint()
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "token-b")
    second = UpstoxFeedConfig.from_env().fingerprint()
    assert first == second


def test_config_rejects_invalid_mode(monkeypatch):
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "token-value")
    monkeypatch.setenv("UPSTOX_FEED_MODE", "invalid")
    with pytest.raises(ValueError, match="Unsupported UPSTOX_FEED_MODE"):
        UpstoxFeedConfig.from_env()
