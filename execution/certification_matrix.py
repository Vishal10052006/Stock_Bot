"""CERT-01 through CERT-12 execution certification matrix.

This module is evidence bookkeeping and fail-closed evaluation only.  It never
authorizes live trading and it does not manufacture provider evidence.

Each certification item has a stable ID, a readiness-gate field, and an
explicit evidence boundary.  A certification run is PASS only when every
required item has status PASS.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class CertificationStatus(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class CertificationItem:
    cert_id: str
    name: str
    gate_field: str
    description: str
    requires_external_evidence: bool = False


@dataclass(frozen=True, slots=True)
class CertificationEvidence:
    cert_id: str
    status: CertificationStatus
    evidence: tuple[str, ...] = ()
    details: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status is CertificationStatus.PASS


@dataclass(frozen=True, slots=True)
class CertificationReport:
    items: tuple[CertificationItem, ...]
    evidence: tuple[CertificationEvidence, ...]

    @property
    def passed(self) -> bool:
        expected = {item.cert_id for item in self.items}
        observed = {record.cert_id for record in self.evidence}
        return (
            expected == observed
            and len(self.items) == 12
            and all(record.passed for record in self.evidence)
        )

    @property
    def failed(self) -> tuple[CertificationEvidence, ...]:
        return tuple(record for record in self.evidence if not record.passed)

    @property
    def missing(self) -> tuple[str, ...]:
        observed = {record.cert_id for record in self.evidence}
        return tuple(item.cert_id for item in self.items if item.cert_id not in observed)


CERTIFICATION_ITEMS: tuple[CertificationItem, ...] = (
    CertificationItem(
        "CERT-01",
        "Broker contract",
        "broker_contract_validated",
        "Broker adapter surface and response contracts are validated.",
    ),
    CertificationItem(
        "CERT-02",
        "Failure matrix",
        "failure_matrix_validated",
        "Timeout, network ambiguity, and broker rejection remain fail-closed.",
    ),
    CertificationItem(
        "CERT-03",
        "Idempotency",
        "idempotency_validated",
        "Duplicate replay cannot create a second broker order.",
    ),
    CertificationItem(
        "CERT-04",
        "Restart recovery",
        "restart_recovery_validated",
        "Execution state can be rehydrated from broker truth without duplicate submission.",
    ),
    CertificationItem(
        "CERT-05",
        "Position reconciliation",
        "reconciliation_validated",
        "Local and broker signed positions reconcile before execution can be considered safe.",
    ),
    CertificationItem(
        "CERT-06",
        "Kill switch",
        "kill_switch_validated",
        "Independent safety controls block execution when the kill switch is active.",
    ),
    CertificationItem(
        "CERT-07",
        "Monitoring",
        "monitoring_validated",
        "Execution status, quantity, fill, rejection, unknown, and latency metrics are observable.",
    ),
    CertificationItem(
        "CERT-08",
        "Paper soak",
        "paper_soak_validated",
        "Paper execution completes without unknown orders or reconciliation errors.",
    ),
    CertificationItem(
        "CERT-09",
        "Backtest/execution parity",
        "backtest_execution_parity_validated",
        "Execution cost assumptions are identical between backtest and execution paths.",
    ),
    CertificationItem(
        "CERT-10",
        "Operational runbook",
        "operational_runbook_validated",
        "Preflight, incident, shutdown, and UNKNOWN-order procedures are defined.",
    ),
    CertificationItem(
        "CERT-11",
        "CI",
        "ci_validated",
        "Required repository regression/CI evidence is explicitly recorded.",
    ),
    CertificationItem(
        "CERT-12",
        "Provider evidence",
        "provider_evidence_validated",
        "Required broker-provider behavior is externally observed and recorded.",
        requires_external_evidence=True,
    ),
)


def certification_items() -> tuple[CertificationItem, ...]:
    """Return the immutable CERT-01..CERT-12 definition."""
    return CERTIFICATION_ITEMS


def build_certification_report(
    evidence: Mapping[str, CertificationEvidence],
) -> CertificationReport:
    """Build a fail-closed certification report from explicit evidence.

    Unknown, missing, duplicate, or malformed certification IDs are never
    converted into PASS.  Provider evidence must be explicitly supplied; this
    function does not infer it from unit tests.
    """
    expected = {item.cert_id for item in CERTIFICATION_ITEMS}
    unknown = set(evidence) - expected
    if unknown:
        raise ValueError(f"unknown certification IDs: {sorted(unknown)}")

    records: list[CertificationEvidence] = []
    for item in CERTIFICATION_ITEMS:
        record = evidence.get(item.cert_id)
        if record is None:
            continue
        if record.cert_id != item.cert_id:
            raise ValueError(f"evidence ID mismatch for {item.cert_id}")
        records.append(record)

    return CertificationReport(CERTIFICATION_ITEMS, tuple(records))


def readiness_gate_values(
    evidence: Mapping[str, CertificationEvidence],
) -> dict[str, bool]:
    """Translate explicit certification evidence into readiness-gate values.

    Missing evidence is False.  This mapping is intentionally non-authorizing:
    callers must still pass it through ProductionReadinessGate and the
    independent live safety gate.
    """
    values = {item.gate_field: False for item in CERTIFICATION_ITEMS}
    by_id = {item.cert_id: item for item in CERTIFICATION_ITEMS}
    for cert_id, record in evidence.items():
        item = by_id.get(cert_id)
        if item is not None:
            values[item.gate_field] = record.passed
    return values


__all__ = [
    "CERTIFICATION_ITEMS",
    "CertificationEvidence",
    "CertificationItem",
    "CertificationReport",
    "CertificationStatus",
    "build_certification_report",
    "certification_items",
    "readiness_gate_values",
]
