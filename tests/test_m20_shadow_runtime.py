"""M20 boot/runtime safety tests.

These tests never connect to Upstox and never touch a broker.
"""

from __future__ import annotations

import pytest

from runtime.config import ShadowRuntimeConfig
from runtime.mode import RuntimeSafety, UnsafeRuntimeModeError, load_runtime_safety


def test_runtime_safety_is_shadow_only():
    """M20 must reject every non-shadow mode."""
    with pytest.raises(UnsafeRuntimeModeError):
        RuntimeSafety(mode="LIVE")

    with pytest.raises(UnsafeRuntimeModeError):
        RuntimeSafety(
            mode="SHADOW",
            live_broker_order_submission=True,
        )


def test_environment_rejects_live_order_flag(monkeypatch):
    """An explicit live-order flag must fail closed."""
    monkeypatch.setenv("STOCK_BOT_MODE", "SHADOW")
    monkeypatch.setenv("STOCK_BOT_LIVE_ORDER_SUBMISSION", "true")

    with pytest.raises(
        UnsafeRuntimeModeError,
        match="forbidden",
    ):
        load_runtime_safety()


def test_environment_defaults_to_shadow(monkeypatch):
    """Missing safety settings must resolve to the safe M20 posture."""
    monkeypatch.delenv("STOCK_BOT_MODE", raising=False)
    monkeypatch.delenv("STOCK_BOT_LIVE_ORDER_SUBMISSION", raising=False)

    safety = load_runtime_safety()

    assert safety.mode == "SHADOW"
    assert safety.live_broker_order_submission is False


def test_environment_rejects_non_shadow_mode(monkeypatch):
    """A non-shadow runtime must never boot."""
    monkeypatch.setenv("STOCK_BOT_MODE", "LIVE")
    monkeypatch.delenv("STOCK_BOT_LIVE_ORDER_SUBMISSION", raising=False)

    with pytest.raises(
        UnsafeRuntimeModeError,
        match="SHADOW",
    ):
        load_runtime_safety()


def test_shadow_config_normalizes_symbols(monkeypatch):
    """Runtime symbols are normalized and deduplicated."""
    monkeypatch.delenv("STOCK_BOT_EVENT_MAX_AGE_SECONDS", raising=False)
    monkeypatch.delenv(
        "STOCK_BOT_EVENT_MAX_FUTURE_SKEW_SECONDS",
        raising=False,
    )
    monkeypatch.delenv(
        "STOCK_BOT_CANDLE_TIMEFRAME_MINUTES",
        raising=False,
    )

    config = ShadowRuntimeConfig.from_env(
        (" tcs ", "RELIANCE", "tcs"),
    )

    assert config.symbols == ("RELIANCE", "TCS")
    assert config.timeframe_minutes == 5


def test_shadow_config_rejects_empty_symbols():
    """An empty symbol set must not boot the market runtime."""
    with pytest.raises(ValueError, match="at least one"):
        ShadowRuntimeConfig.from_env(())
