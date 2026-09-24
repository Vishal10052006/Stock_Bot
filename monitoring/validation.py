from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class MonitoringValidationResult:
    passed: bool
    checks: tuple[str,...]=()
    failures: tuple[str,...]=()

def validate_monitoring_snapshot(snapshot):
    checks=[]; failures=[]
    if snapshot.timestamp: checks.append("snapshot.timestamp")
    else: failures.append("snapshot.timestamp")
    if any(value is None for value in snapshot.metrics.values()): failures.append("snapshot.metrics.no_null_values")
    else: checks.append("snapshot.metrics.no_null_values")
    fps=[a.fingerprint for a in snapshot.alerts]
    if len(fps)!=len(set(fps)): failures.append("snapshot.alerts.unique_fingerprints")
    else: checks.append("snapshot.alerts.unique_fingerprints")
    if all(h.component for h in snapshot.health): checks.append("health.components")
    else: failures.append("health.components")
    return MonitoringValidationResult(not failures,tuple(checks),tuple(failures))
