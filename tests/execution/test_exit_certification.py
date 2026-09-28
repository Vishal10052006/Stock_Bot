"""PAPER-04 approved exit execution certification tests."""
from execution.exit_certification import run_exit_execution_certification

def test_exit_execution_certification_matrix_passes():
    report = run_exit_execution_certification()
    assert report.passed, report.failed
    assert not report.failed
    assert {case.name for case in report.cases} == {
        "full_long_stop_exit",
        "full_short_target_exit",
        "partial_long_time_exit",
        "partial_short_exit",
        "exit_cannot_exceed_position",
        "exit_direction_must_oppose_position",
        "duplicate_exit_is_idempotent",
        "exit_from_flat_position_is_rejected",
    }
