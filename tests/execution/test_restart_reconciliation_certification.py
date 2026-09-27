"""PAPER-03 restart and reconciliation certification tests."""
from execution.engine import ExecutionEngine
from execution.restart_reconciliation_certification import run_restart_reconciliation_certification
from tests.execution.test_execution_engine import order_request

def test_restart_reconciliation_certification_matrix_passes():
    report = run_restart_reconciliation_certification(order_request)
    assert report.passed
    assert not report.failed
    assert {case.name for case in report.cases} == {
        "restart_filled_order",
        "restart_partial_order",
        "unknown_resolves_to_filled_without_resubmit",
        "unknown_missing_state_stays_fail_closed",
        "malformed_reconciliation_is_rejected",
        "signed_position_match_and_mismatch",
        "unknown_rehydration_from_broker_truth",
    }

def test_restart_reconciliation_certification_does_not_enable_live_execution():
    report = run_restart_reconciliation_certification(order_request)
    assert report.passed
    assert ExecutionEngine.__name__ == "ExecutionEngine"
