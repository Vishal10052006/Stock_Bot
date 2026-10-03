from __future__ import annotations

from pathlib import Path

import pytest

from scripts.validate_live_review_env import (
    PreflightError,
    validate_live_review_environment,
)


def _configure(monkeypatch, tmp_path: Path) -> None:
    values = {
        "UPSTOX_ACCESS_TOKEN": "test-token",
        "UPSTOX_INSTRUMENT_MAP": '{"RELIANCE":"NSE_EQ|test"}',
        "STOCK_BOT_RISK_CONTEXT_MAX_AGE_SECONDS": "30",
        "STOCK_BOT_RISK_CONTEXT_TIMEOUT_SECONDS": "5",
        "STOCK_BOT_RISK_DAY_STATE_PATH": str(tmp_path / "risk-day.json"),
        "STOCK_BOT_RISK_API_BASE_URL": "https://api.example.test",
        "STOCK_BOT_RISK_EXCHANGE": "NSE",
        "STOCK_BOT_RISK_SEGMENT": "SEC",
        "STOCK_BOT_RISK_TIMEZONE": "Asia/Kolkata",
        "STOCK_BOT_RISK_CONTEXT_SOURCE": "upstox-read-only",
        "STOCK_BOT_RISK_ACCESS_TOKEN_ENV": "TEST_UPSTOX_TOKEN",
        "TEST_UPSTOX_TOKEN": "test-token",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "risk-day.json").parent.mkdir(parents=True, exist_ok=True)


def test_live_review_preflight_accepts_valid_local_configuration(
    monkeypatch, tmp_path: Path
) -> None:
    _configure(monkeypatch, tmp_path)

    result = validate_live_review_environment()

    assert result["network_calls"] is False
    assert result["broker_orders"] is False
    assert result["execution_authority"] == "HUMAN_MANUAL_BUY_SELL"


@pytest.mark.parametrize(
    "name",
    [
        "UPSTOX_ACCESS_TOKEN",
        "UPSTOX_INSTRUMENT_MAP",
        "STOCK_BOT_RISK_CONTEXT_MAX_AGE_SECONDS",
        "STOCK_BOT_RISK_CONTEXT_TIMEOUT_SECONDS",
        "STOCK_BOT_RISK_DAY_STATE_PATH",
        "STOCK_BOT_RISK_API_BASE_URL",
        "STOCK_BOT_RISK_EXCHANGE",
        "STOCK_BOT_RISK_SEGMENT",
        "STOCK_BOT_RISK_TIMEZONE",
        "STOCK_BOT_RISK_CONTEXT_SOURCE",
        "STOCK_BOT_RISK_ACCESS_TOKEN_ENV",
    ],
)
def test_live_review_preflight_rejects_missing_required_setting(
    monkeypatch, tmp_path: Path, name: str
) -> None:
    _configure(monkeypatch, tmp_path)
    monkeypatch.delenv(name, raising=False)

    with pytest.raises(PreflightError):
        validate_live_review_environment()


def test_live_review_preflight_rejects_missing_token_named_by_risk_setting(
    monkeypatch, tmp_path: Path
) -> None:
    _configure(monkeypatch, tmp_path)
    monkeypatch.delenv("TEST_UPSTOX_TOKEN", raising=False)

    with pytest.raises(PreflightError, match="TEST_UPSTOX_TOKEN"):
        validate_live_review_environment()


def test_live_review_preflight_rejects_invalid_instrument_map(
    monkeypatch, tmp_path: Path
) -> None:
    _configure(monkeypatch, tmp_path)
    monkeypatch.setenv("UPSTOX_INSTRUMENT_MAP", "not-json")

    with pytest.raises(PreflightError, match="UPSTOX_INSTRUMENT_MAP"):
        validate_live_review_environment()


def test_live_review_preflight_rejects_missing_day_state_parent(
    monkeypatch, tmp_path: Path
) -> None:
    _configure(monkeypatch, tmp_path)
    monkeypatch.setenv(
        "STOCK_BOT_RISK_DAY_STATE_PATH",
        str(tmp_path / "missing" / "risk-day.json"),
    )

    with pytest.raises(PreflightError, match="parent directory"):
        validate_live_review_environment()
