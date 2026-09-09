"""Unit tests for Upstox feed configuration."""

import pytest

from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig


def test_config_reads_access_token_from_environment(monkeypatch):
    """Configuration should load runtime secrets without source changes."""
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "token-value")

    config = UpstoxFeedConfig.from_env()

    assert config.access_token == "token-value"
    assert config.mode == "ltpc"
    assert config.timeout_seconds == 10.0


def test_config_requires_access_token(monkeypatch):
    """The live feed must never start without an access token."""
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)

    with pytest.raises(ValueError, match="UPSTOX_ACCESS_TOKEN"):
        UpstoxFeedConfig.from_env()


def test_config_rejects_invalid_mode(monkeypatch):
    """Only documented feed modes are accepted."""
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "token-value")
    monkeypatch.setenv("UPSTOX_FEED_MODE", "invalid")

    with pytest.raises(ValueError, match="Unsupported UPSTOX_FEED_MODE"):
        UpstoxFeedConfig.from_env()
