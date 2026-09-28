from execution.production_gate_certification import run_production_gate_certification


def test_production_gate_certification_passes():
    report = run_production_gate_certification()
    assert report.passed
    assert not report.failed


def test_production_gate_certification_cases():
    report = run_production_gate_certification()
    assert [case.name for case in report.cases] == [
        "empty_gate_set_is_blocked",
        "all_required_gates_are_required",
        "all_validated_gates_pass",
        "safety_live_lock_remains_independent",
        "readiness_gate_does_not_authorize_live_execution",
    ]
