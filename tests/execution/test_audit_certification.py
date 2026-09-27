"""PAPER-05 durable execution audit certification tests."""

from execution.audit_certification import run_audit_certification


def test_audit_certification_matrix_passes():
    report = run_audit_certification()

    assert report.passed, report.failed
    assert {case.name for case in report.cases} == {
        "decision_order_fill_position_lineage",
        "lifecycle_events_are_durable",
        "duplicate_audit_identity_is_rejected",
        "audit_survives_restart",
        "malformed_audit_fails_closed",
    }
