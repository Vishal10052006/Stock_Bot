"""M20 monitoring telemetry bridge.

The bridge sends real-market shadow observations into the existing
MonitoringRuntime. Monitoring remains observational and cannot authorize,
modify, or submit trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from market.data.metrics import DataQualitySnapshot
from monitoring.runtime import MonitoringRuntime


@dataclass(slots=True)
class ShadowMonitoringBridge:
    """Publish M20 market-data telemetry to the central monitor."""

    monitoring: MonitoringRuntime

    def observe_market_data(self, snapshot: DataQualitySnapshot) -> dict[str, Any]:
        """Record data-quality telemetry without changing trading authority."""
        result = self.monitoring.observe_data_quality(snapshot)
        return {
            "component": result.component,
            "observed": result.observed,
            "metrics_recorded": result.metrics_recorded,
            "alerts_emitted": result.alerts_emitted,
            "live_broker_order_submission": False,
        }

    def dashboard(self) -> dict[str, Any]:
        """Return the existing monitoring dashboard snapshot."""
        return self.monitoring.dashboard()
