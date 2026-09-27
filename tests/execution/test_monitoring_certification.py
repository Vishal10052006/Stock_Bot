import pandas as pd

from execution.engine import ExecutionEngine
from execution.monitoring_certification import run_monitoring_certification
from execution.trading_execution import ExecutionAuthorization, ExecutionAuthorizationStatus
from trading.strategy.models import StrategyDirection


def authorization(quantity: float = 100.0) -> ExecutionAuthorization:
    return ExecutionAuthorization(
        timestamp=pd.Timestamp("2026-09-27T10:00:00+05:30"),
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="PAPER-06 certification",
        risk_version="RISK-v1.0",
        approved_quantity=quantity,
        approved_notional=quantity * 100.0,
        risk_decision_id="paper06-risk",
    )


def order_factory():
    return ExecutionEngine.from_authorization(
        authorization(),
        decision_id="paper06-order",
    )


def test_monitoring_certification_passes():
    report = run_monitoring_certification(order_factory)
    assert report.passed
    assert not report.failed


def test_monitoring_certification_has_expected_cases():
    report = run_monitoring_certification(order_factory)
    assert [case.name for case in report.cases] == [
        "full_fill_metrics",
        "partial_fill_metrics",
        "rejection_metrics",
        "unknown_observed_without_retry",
        "fees_are_observable",
        "reconciliation_failure_is_observable",
        "monitoring_policy_is_descriptive_only",
        "monitor_is_observation_only",
    ]
