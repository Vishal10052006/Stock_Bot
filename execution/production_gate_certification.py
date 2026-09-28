"""Final execution production-readiness gate certification.

This certifies the software gate evaluation itself. It does not authorize live
broker execution and does not claim provider/live-market readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from execution.production import ProductionGateStatus, ProductionReadinessGate
from execution.safety import IndependentSafetyGate, SafetyBlock, SafetyState


@dataclass(frozen=True, slots=True)
class ProductionGateCase:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ProductionGateCertificationReport:
    cases: tuple[ProductionGateCase, ...]

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(case.passed for case in self.cases)

    @property
    def failed(self) -> tuple[ProductionGateCase, ...]:
        return tuple(case for case in self.cases if not case.passed)


def _case(name: str, check: Callable[[], None]) -> ProductionGateCase:
    try:
        check()
    except Exception as exc:
        return ProductionGateCase(name, False, f"{type(exc).__name__}: {exc}")
    return ProductionGateCase(name, True, "PASS")


def run_production_gate_certification() -> ProductionGateCertificationReport:
    """Certify fail-closed readiness semantics and live-lock preservation."""

    def empty_gate_set_is_blocked() -> None:
        report = ProductionReadinessGate().evaluate({})
        assert report.status is ProductionGateStatus.BLOCKED
        assert set(report.failed_gates) == set(ProductionReadinessGate.FIELDS)

    def all_required_gates_are_required() -> None:
        fields = ProductionReadinessGate.FIELDS
        for missing in fields:
            gates = {field: True for field in fields}
            gates[missing] = False
            report = ProductionReadinessGate().evaluate(gates)
            assert not report.ready
            assert missing in report.failed_gates

    def all_validated_gates_pass() -> None:
        gates = {field: True for field in ProductionReadinessGate.FIELDS}
        report = ProductionReadinessGate().evaluate(gates)
        assert report.status is ProductionGateStatus.PASS
        assert report.ready
        assert report.failed_gates == ()

    def safety_live_lock_remains_independent() -> None:
        decision = IndependentSafetyGate().evaluate(
            SafetyState(live_execution_enabled=False)
        )
        assert not decision.allowed
        assert decision.block is SafetyBlock.LIVE_LOCKED

    def readiness_gate_does_not_authorize_live_execution() -> None:
        gates = {field: True for field in ProductionReadinessGate.FIELDS}
        report = ProductionReadinessGate().evaluate(gates)
        assert report.ready

        safety = IndependentSafetyGate().evaluate(SafetyState())
        assert not safety.allowed
        assert safety.block is SafetyBlock.LIVE_LOCKED

    cases = (
        _case("empty_gate_set_is_blocked", empty_gate_set_is_blocked),
        _case("all_required_gates_are_required", all_required_gates_are_required),
        _case("all_validated_gates_pass", all_validated_gates_pass),
        _case("safety_live_lock_remains_independent", safety_live_lock_remains_independent),
        _case("readiness_gate_does_not_authorize_live_execution", readiness_gate_does_not_authorize_live_execution),
    )
    return ProductionGateCertificationReport(cases)


__all__ = [
    "ProductionGateCase",
    "ProductionGateCertificationReport",
    "run_production_gate_certification",
]
