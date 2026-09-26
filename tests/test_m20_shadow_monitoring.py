"""Tests for the M20 monitoring telemetry bridge."""

from runtime.shadow_monitoring import ShadowMonitoringBridge
from monitoring.runtime import MonitoringRuntime
from market.data.metrics import DataQualityMetrics


def test_shadow_monitoring_bridge_records_market_quality() -> None:
    metrics = DataQualityMetrics()
    bridge = ShadowMonitoringBridge(monitoring=MonitoringRuntime())

    result = bridge.observe_market_data(metrics.snapshot())

    assert result["component"] == "market_data"
    assert result["observed"] is True
    assert result["live_broker_order_submission"] is False


def test_shadow_monitoring_bridge_exposes_dashboard() -> None:
    bridge = ShadowMonitoringBridge(monitoring=MonitoringRuntime())

    dashboard = bridge.dashboard()

    assert isinstance(dashboard, dict)
