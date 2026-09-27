"""PAPER-08 / E17 Upstox adapter and live-safety certification.

This module certifies the existing provider adapter boundary and independent
safety gate. It does not enable live trading and performs no real broker call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from execution.adapters.upstox import UpstoxAdapterConfig, UpstoxBrokerAdapter
from execution.safety import IndependentSafetyGate, SafetyBlock, SafetyState
from execution.adapters.base import BrokerAdapter
from execution.engine import (
    Fill,
    OrderRequest,
    OrderSnapshot,
    PositionSnapshot,
)


@dataclass(frozen=True, slots=True)
class LiveSafetyCase:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class LiveSafetyReport:
    cases: tuple[LiveSafetyCase, ...]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def failed(self) -> tuple[LiveSafetyCase, ...]:
        return tuple(case for case in self.cases if not case.passed)


def _case(name: str, check: Callable[[], None]) -> LiveSafetyCase:
    try:
        check()
    except Exception as exc:
        return LiveSafetyCase(name, False, f"{type(exc).__name__}: {exc}")
    return LiveSafetyCase(name, True, "PASS")


def run_live_safety_certification() -> LiveSafetyReport:
    """Certify E17 safety/provider boundaries without live submission."""

    def live_is_locked_by_default() -> None:
        config = UpstoxAdapterConfig(api_base_url="https://api-hft.upstox.com")
        assert config.enabled is False
        decision = IndependentSafetyGate().evaluate(SafetyState())
        assert not decision.allowed
        assert decision.block is SafetyBlock.LIVE_LOCKED

    def kill_switch_blocks_even_when_live_enabled() -> None:
        decision = IndependentSafetyGate().evaluate(
            SafetyState(live_execution_enabled=True, kill_switch_active=True)
        )
        assert not decision.allowed
        assert decision.block is SafetyBlock.KILL_SWITCH

    def stale_data_blocks_before_provider_routing() -> None:
        decision = IndependentSafetyGate().evaluate(
            SafetyState(live_execution_enabled=True, stale_data=True)
        )
        assert not decision.allowed
        assert decision.block is SafetyBlock.STALE_DATA

    def invalid_data_quality_blocks() -> None:
        decision = IndependentSafetyGate().evaluate(
            SafetyState(live_execution_enabled=True, data_quality_ok=False)
        )
        assert not decision.allowed
        assert decision.block is SafetyBlock.DATA_QUALITY

    def closed_session_blocks() -> None:
        decision = IndependentSafetyGate().evaluate(
            SafetyState(live_execution_enabled=True, session_open=False)
        )
        assert not decision.allowed
        assert decision.block is SafetyBlock.SESSION_CLOSED

    def provider_disabled_is_fail_closed() -> None:
        adapter = UpstoxBrokerAdapter(
            UpstoxAdapterConfig(api_base_url="https://api-hft.upstox.com"),
            client=object(),
        )
        try:
            adapter.positions()
        except RuntimeError as exc:
            assert "disabled" in str(exc)
            return
        raise AssertionError("disabled Upstox adapter accepted a provider call")

    def enabled_provider_requires_injected_client() -> None:
        adapter = UpstoxBrokerAdapter(
            UpstoxAdapterConfig(
                api_base_url="https://api-hft.upstox.com",
                enabled=True,
            )
        )
        try:
            adapter.positions()
        except RuntimeError as exc:
            assert "No Upstox client" in str(exc)
            return
        raise AssertionError("enabled adapter created its own client")

    cases = (
        _case("live_is_locked_by_default", live_is_locked_by_default),
        _case("kill_switch_blocks_even_when_live_enabled", kill_switch_blocks_even_when_live_enabled),
        _case("stale_data_blocks_before_provider_routing", stale_data_blocks_before_provider_routing),
        _case("invalid_data_quality_blocks", invalid_data_quality_blocks),
        _case("closed_session_blocks", closed_session_blocks),
        _case("provider_disabled_is_fail_closed", provider_disabled_is_fail_closed),
        _case("enabled_provider_requires_injected_client", enabled_provider_requires_injected_client),
    )
    return LiveSafetyReport(cases)


__all__ = ["LiveSafetyCase", "LiveSafetyReport", "run_live_safety_certification"]
