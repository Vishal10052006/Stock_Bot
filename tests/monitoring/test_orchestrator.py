from monitoring.alerts import AlertSeverity
from monitoring.engine import MonitoringEngine
from monitoring.orchestrator import AlertOrchestrator, AlertRule


def test_alert_orchestrator_applies_central_severity_and_correlation():
    engine = MonitoringEngine()
    orchestrator = AlertOrchestrator()

    alert = orchestrator.emit(
        engine,
        code="ERROR_RATE_EXCEEDED",
        message="error threshold breached",
        component="system",
    )

    assert alert is not None
    assert alert.severity is AlertSeverity.CRITICAL
    assert alert.metadata["correlation_id"]
    assert alert.metadata["occurrence_count"] == 1


def test_alert_orchestrator_escalates_repeated_condition():
    engine = MonitoringEngine()
    orchestrator = AlertOrchestrator(
        rules={
            "TEST_REPEAT": AlertRule(
                AlertSeverity.WARNING,
                escalation_after=3,
                escalation_severity=AlertSeverity.EMERGENCY,
            )
        }
    )

    for _ in range(2):
        orchestrator.emit(
            engine,
            code="TEST_REPEAT",
            message="repeat",
            component="test",
        )

    third = orchestrator.emit(
        engine,
        code="TEST_REPEAT",
        message="repeat",
        component="test",
    )

    assert third is not None
    assert third.severity is AlertSeverity.EMERGENCY
    assert third.metadata["occurrence_count"] == 3


def test_alert_orchestrator_summary_is_observational():
    engine = MonitoringEngine()
    orchestrator = AlertOrchestrator()
    orchestrator.emit(
        engine,
        code="EXECUTION_REJECTION_RATE_HIGH",
        message="rejections",
        component="execution",
    )
    orchestrator.emit(
        engine,
        code="FEATURE_DRIFT_WARNING",
        message="feature drift",
        component="feature",
    )

    summary = orchestrator.summary(engine.snapshot().alerts)

    assert summary.total == 2
    assert summary.by_severity["WARNING"] == 2
    assert summary.by_code["FEATURE_DRIFT_WARNING"] == 1
    assert len(summary.active_fingerprints) == 2
