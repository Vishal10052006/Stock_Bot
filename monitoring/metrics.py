from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import math

@dataclass(frozen=True, slots=True)
class MetricSample:
    """One timestamped scalar metric."""
    name: str
    value: float
    timestamp: str
    labels: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.timestamp.strip():
            raise ValueError("name and timestamp must be non-empty")
        value = float(self.value)
        if not math.isfinite(value):
            raise ValueError("value must be finite")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "labels", dict(self.labels or {}))

class MetricsCollector:
    """Bounded in-memory collector for local monitoring."""
    def __init__(self, max_samples: int = 50_000) -> None:
        if max_samples <= 0:
            raise ValueError("max_samples must be positive")
        self.max_samples = int(max_samples)
        self._samples: list[MetricSample] = []

    def record(self, name: str, value: float, *, labels: dict[str, str] | None = None, timestamp: str | None = None) -> MetricSample:
        sample = MetricSample(name, value, timestamp or datetime.now(timezone.utc).isoformat(), labels)
        self._samples.append(sample)
        if len(self._samples) > self.max_samples:
            del self._samples[:len(self._samples) - self.max_samples]
        return sample

    def snapshot(self) -> tuple[MetricSample, ...]:
        return tuple(self._samples)

    def values(self, name: str) -> tuple[float, ...]:
        return tuple(s.value for s in self._samples if s.name == name)

    def latest(self, name: str) -> MetricSample | None:
        for sample in reversed(self._samples):
            if sample.name == name:
                return sample
        return None
