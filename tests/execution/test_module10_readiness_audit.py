"""Tests for the Module-10 evidence-driven readiness audit."""

from pathlib import Path

import pytest

from execution.certification_matrix import CertificationStatus
from execution.production import ProductionGateStatus
from scripts.audit_module10_readiness import (
    build_module10_audit,
    parse_certification_evidence,
)


EVIDENCE = Path("docs/EXECUTION_CERTIFICATION_EVIDENCE.md")


def test_module10_audit_reads_all_certification_rows():
    statuses = parse_certification_evidence(EVIDENCE)

    assert tuple(statuses) == tuple(f"CERT-{index:02d}" for index in range(1, 13))
    assert statuses["CERT-08"] is CertificationStatus.PARTIAL
    assert statuses["CERT-12"] is CertificationStatus.PARTIAL


def test_module10_audit_fails_closed_for_current_recorded_evidence():
    audit = build_module10_audit(parse_certification_evidence(EVIDENCE))

    assert audit.production_gate_status == ProductionGateStatus.BLOCKED.value
    assert "paper_soak_validated" in audit.failed_production_gates
    assert "provider_evidence_validated" in audit.failed_production_gates
    assert "CERT-08" in audit.unresolved_external_items
    assert "CERT-12" in audit.unresolved_external_items
    assert audit.live_locked
    assert audit.overall_status == "BLOCKED"


def test_module10_parser_rejects_missing_certification(tmp_path: Path):
    evidence = tmp_path / "evidence.md"
    evidence.write_text(
        "| ID | Status | Evidence boundary |\\n"
        "|---|---|---|\\n"
        "| CERT-01 | PASS | example |\\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="table mismatch"):
        parse_certification_evidence(evidence)


def test_module10_parser_rejects_duplicate_certification(tmp_path: Path):
    rows = [
        "| ID | Status | Evidence boundary |",
        "|---|---|---|",
    ]
    for index in range(1, 13):
        rows.append(f"| CERT-{index:02d} | PASS | example |")
    rows.insert(2, "| CERT-01 | PASS | duplicate |")

    evidence = tmp_path / "evidence.md"
    evidence.write_text("\\n".join(rows), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate certification row"):
        parse_certification_evidence(evidence)
