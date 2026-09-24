from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .dashboard import snapshot_payload
from .engine import MonitoringEngine
from .readiness import MonitoringReadiness, ReadinessCheck, evaluate_readiness
from .validation import validate_monitoring_snapshot

@dataclass(frozen=True, slots=True)
class MonitoringIntegrationReport:
    readiness: MonitoringReadiness
    validation_passed: bool
    dashboard_payload: dict[str,Any]

class MonitoringIntegration:
    def __init__(self,engine: MonitoringEngine): self.engine=engine
    def report(self):
        snapshot=self.engine.snapshot()
        validation=validate_monitoring_snapshot(snapshot)
        checks=(ReadinessCheck("system.snapshot_validation",validation.passed,"; ".join(validation.failures)),ReadinessCheck("system.monitoring_engine",True,"monitoring engine available"))
        return MonitoringIntegrationReport(evaluate_readiness(checks),validation.passed,snapshot_payload(snapshot))
