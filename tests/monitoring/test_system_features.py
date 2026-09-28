from monitoring.features import (
    FeatureMonitoringSnapshot,
    evaluate_feature_monitoring,
)
from monitoring.system import (
    SystemMonitoringSnapshot,
    evaluate_system_monitoring,
)


def test_system_monitoring_emits_error_and_stale_alerts() -> None:
    metrics, alerts = evaluate_system_monitoring(
        SystemMonitoringSnapshot(
            total_events=100,
            failed_events=10,
            stale_events=20,
            duplicate_events=2,
            invalid_events=3,
        ),
        max_error_rate=0.05,
        max_stale_rate=0.10,
    )

    assert metrics["error_rate"] == 0.10
    assert metrics["stale_rate"] == 0.20
    assert alerts == ("ERROR_RATE_EXCEEDED", "STALE_RATE_EXCEEDED")


def test_feature_monitoring_detects_distribution_drift() -> None:
    metrics, reports, alerts = evaluate_feature_monitoring(
        FeatureMonitoringSnapshot(
            feature_count=10,
            invalid_count=1,
            missing_count=2,
            reference_values=(0.0, 0.0, 0.0, 0.0),
            current_values=(1.0, 1.0, 1.0, 1.0),
        ),
        max_psi=0.20,
        warning_psi=0.10,
    )

    assert metrics["invalid_rate"] == 0.1
    assert metrics["missing_rate"] == 0.2
    assert len(reports) == 1
    assert reports[0].status == "CRITICAL"
    assert alerts == ("FEATURE_DRIFT_EXCEEDED",)
