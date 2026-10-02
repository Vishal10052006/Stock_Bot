"""Module-10 production-readiness audit.

This command is intentionally evidence-driven and fail-closed. It reads the
recorded CERT-01..CERT-12 evidence document, validates the current software
readiness-gate semantics, and reports unresolved evidence without upgrading
PARTIAL/UNVERIFIED items.

It never authorizes live execution.
"""

from __future__ import annotations


# Allow direct `python scripts/audit_module10_readiness.py` execution from the repository root.
# GitHub Actions invokes this file as a script rather than with `python -m`.
import sys
from pathlib import Path as _Path

_REPOSITORY_ROOT = _Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from execution.certification_matrix import (
    CERTIFICATION_ITEMS,
    CertificationEvidence,
    CertificationStatus,
    build_certification_report,
    readiness_gate_values,
)
from execution.production import ProductionGateStatus, ProductionReadinessGate
from execution.production_gate_certification import run_production_gate_certification
from execution.safety import IndependentSafetyGate, SafetyState

STATUS_RE = re.compile(
    r"^\|\s*(CERT-\d{2})\s*\|\s*"
    r"(PASS|PARTIAL|BLOCKED|UNVERIFIED|FAILED)\s*\|\s*(.*?)\s*\|$"
)
EXPECTED_IDS = tuple(item.cert_id for item in CERTIFICATION_ITEMS)


@dataclass(frozen=True, slots=True)
class Module10Audit:
    recorded_statuses: dict[str, str]
    production_gate_status: str
    failed_production_gates: tuple[str, ...]
    software_gate_certification_passed: bool
    live_locked: bool
    unresolved_external_items: tuple[str, ...]
    overall_status: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_certification_evidence(path: Path) -> dict[str, CertificationStatus]:
    """Parse the authoritative CERT-01..CERT-12 status table strictly."""
    if not path.is_file():
        raise FileNotFoundError(f"evidence document not found: {path}")

    statuses: dict[str, CertificationStatus] = {}
    in_table = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "| ID | Status | Evidence boundary |":
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        match = STATUS_RE.match(line)
        if match is None:
            if line.startswith("|---"):
                continue
            raise ValueError(f"malformed certification row: {raw_line!r}")
        cert_id, status, _boundary = match.groups()
        if cert_id in statuses:
            raise ValueError(f"duplicate certification row: {cert_id}")
        statuses[cert_id] = CertificationStatus(status)

    if tuple(statuses) != EXPECTED_IDS:
        missing = [item for item in EXPECTED_IDS if item not in statuses]
        extra = [item for item in statuses if item not in EXPECTED_IDS]
        raise ValueError(
            "CERT-01..CERT-12 table mismatch: "
            f"missing={missing} extra={extra}"
        )
    return statuses


def build_module10_audit(
    statuses: Mapping[str, CertificationStatus],
) -> Module10Audit:
    """Evaluate recorded evidence against current fail-closed gate semantics."""
    evidence = {
        cert_id: CertificationEvidence(
            cert_id=cert_id,
            status=status,
            evidence=(f"recorded in docs/EXECUTION_CERTIFICATION_EVIDENCE.md: {status.value}",),
        )
        for cert_id, status in statuses.items()
    }
    certification_report = build_certification_report(evidence)

    gates = readiness_gate_values(evidence)
    # This is a safety property of the local software configuration, not an
    # assertion of live broker readiness.
    safety = IndependentSafetyGate().evaluate(SafetyState(live_execution_enabled=False))
    gates["live_lock_validated"] = not safety.allowed

    production = ProductionReadinessGate().evaluate(gates)
    software_certification = run_production_gate_certification()

    unresolved = tuple(
        cert_id
        for cert_id, status in statuses.items()
        if status is not CertificationStatus.PASS
    )
    if not software_certification.passed:
        unresolved = unresolved + ("PRODUCTION_GATE_CERTIFICATION",)

    overall = (
        "PASS"
        if certification_report.passed
        and production.status is ProductionGateStatus.PASS
        and software_certification.passed
        else "BLOCKED"
    )

    return Module10Audit(
        recorded_statuses={cert_id: status.value for cert_id, status in statuses.items()},
        production_gate_status=production.status.value,
        failed_production_gates=production.failed_gates,
        software_gate_certification_passed=software_certification.passed,
        live_locked=not safety.allowed,
        unresolved_external_items=unresolved,
        overall_status=overall,
    )


def render_human_report(audit: Module10Audit) -> str:
    lines = [
        "MODULE 10 — PRODUCTION READINESS AUDIT",
        "=" * 46,
        f"Overall: {audit.overall_status}",
        f"Production gate: {audit.production_gate_status}",
        f"Live locked: {audit.live_locked}",
        f"Software gate certification: {audit.software_gate_certification_passed}",
        "",
        "Recorded certification status:",
    ]
    lines.extend(
        f"  {cert_id}: {status}"
        for cert_id, status in audit.recorded_statuses.items()
    )
    lines.append("")
    lines.append("Failed production gates:")
    lines.extend(f"  - {gate}" for gate in audit.failed_production_gates) or lines.append(
        "  - none"
    )
    lines.append("")
    lines.append("Unresolved evidence:")
    lines.extend(
        f"  - {item}" for item in audit.unresolved_external_items
    ) or lines.append("  - none")
    lines.append("")
    lines.append("Live execution remains independently locked; this audit is non-authorizing.")
    return "\\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("docs/EXECUTION_CERTIFICATION_EVIDENCE.md"),
        help="path to the recorded CERT-01..CERT-12 evidence document",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit machine-readable JSON",
    )
    args = parser.parse_args()

    audit = build_module10_audit(parse_certification_evidence(args.evidence))
    if args.as_json:
        print(json.dumps(audit.as_dict(), indent=2, sort_keys=True))
    else:
        print(render_human_report(audit))

    return 0 if audit.overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
