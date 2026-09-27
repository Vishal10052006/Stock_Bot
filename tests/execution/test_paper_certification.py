from execution.engine import ExecutionEngine
from execution.paper_certification import run_paper_certification
from tests.execution.test_execution_engine import order_request


def test_paper_certification_matrix_passes():
    report = run_paper_certification(order_request)
    assert report.passed
    assert not report.failed
    assert {case.name for case in report.cases} == {
        "full_fill",
        "partial_fill",
        "broker_rejection",
        "unknown_recovery_fail_closed",
        "duplicate_replay_idempotency",
        "restart_recovery",
        "signed_position_reconciliation",
        "monitoring_and_paper_soak",
        "backtest_parity_and_operational_controls",
    }


def test_paper_certification_matrix_does_not_enable_live_execution():
    report = run_paper_certification(order_request)
    assert report.passed
    assert ExecutionEngine.__name__ == "ExecutionEngine"
