from __future__ import annotations

from monitoring.empirical_completion import validate_monitoring_report


def _valid_payload() -> dict[str, object]:
    return {
        "status": "EVIDENCE_VALIDATED",
        "evidence_fingerprint": "a" * 64,
        "source_run_id": "run-1",
        "steps": 100,
        "signal_count": 10,
        "fill_count": 2,
        "latency_observation_count": 2,
        "drawdown_observation_count": 100,
        "operational_event_count": 100,
        "stale_event_count": 0,
        "calibration_observation_count": 0,
        "false_signal_count": 0,
    }


def test_monitoring_completion_accepts_deterministic_baseline_without_calibration() -> None:
    report = validate_monitoring_report(_valid_payload())
    assert report.valid is True
    assert report.status == "COMPLETE"


def test_monitoring_completion_rejects_invalid_count_relationship() -> None:
    payload = _valid_payload()
    payload["fill_count"] = 11
    report = validate_monitoring_report(payload)
    assert report.valid is False
    assert any("fills <= signals" in gate.name for gate in report.gates)


def test_monitoring_completion_requires_empirical_status_and_observations() -> None:
    payload = _valid_payload()
    payload["status"] = "STRUCTURAL_ONLY"
    payload["operational_event_count"] = 0
    report = validate_monitoring_report(payload)
    assert report.valid is False
    assert any(gate.name == "M-20 evidence status" and not gate.passed for gate in report.gates)
    assert any(gate.name == "M-24 operational observability" and not gate.passed for gate in report.gates)
