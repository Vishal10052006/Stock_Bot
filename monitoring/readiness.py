from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class ReadinessStatus(str, Enum):
    READY="READY"; DEGRADED="DEGRADED"; BLOCKED="BLOCKED"; UNKNOWN="UNKNOWN"

@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    name: str
    passed: bool
    message: str = ""
    def __post_init__(self):
        if not self.name.strip(): raise ValueError("name must be non-empty")

@dataclass(frozen=True, slots=True)
class MonitoringReadiness:
    status: ReadinessStatus
    checks: tuple[ReadinessCheck,...]=()
    reason: str=""
    
def evaluate_readiness(checks):
    checks=tuple(checks)
    if not checks: return MonitoringReadiness(ReadinessStatus.UNKNOWN,(), "no readiness evidence")
    failures=tuple(c for c in checks if not c.passed)
    if not failures: return MonitoringReadiness(ReadinessStatus.READY,checks,"all monitoring checks passed")
    critical=any(c.name.startswith(("data.","system.","journal.")) for c in failures)
    return MonitoringReadiness(ReadinessStatus.BLOCKED if critical else ReadinessStatus.DEGRADED,checks,"; ".join(c.message or c.name for c in failures))
