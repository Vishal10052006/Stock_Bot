from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any

class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True, slots=True)
class ComponentHealth:
    """Immutable operational health observation."""
    component: str
    status: HealthStatus
    observed_at: str
    message: str = ""
    latency_seconds: float | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.component.strip():
            raise ValueError("component must be non-empty")
        if not self.observed_at.strip():
            raise ValueError("observed_at must be non-empty")
        if self.latency_seconds is not None and self.latency_seconds < 0:
            raise ValueError("latency_seconds must be non-negative")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
