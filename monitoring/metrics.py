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
        self._latest_by_name: dict[str, MetricSample] = {}

    def record(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
        timestamp: str | None = None,
    ) -> MetricSample:
        sample = MetricSample(
            name,
            value,
            timestamp or datetime.now(timezone.utc).isoformat(),
            labels,
        )
        self._samples.append(sample)
        self._latest_by_name[name] = sample

        if len(self._samples) > self.max_samples:
            trim_count = len(self._samples) - self.max_samples
            del self._samples[:trim_count]
            # A trimmed sample may have been the latest retained sample for
            # its metric name. Rebuild only on the bounded-history eviction
            # path so latest-value reads remain O(unique metric names).
            self._latest_by_name = {
                retained.name: retained for retained in self._samples
            }

        return sample

    def snapshot(self) -> tuple[MetricSample, ...]:
        """Return the bounded raw sample history."""
        return tuple(self._samples)

    def latest_values(self) -> dict[str, float]:
        """Return the latest value for each metric name in O(unique names)."""
        return {
            name: sample.value
            for name, sample in self._latest_by_name.items()
        }

    def values(self, name: str) -> tuple[float, ...]:
        return tuple(s.value for s in self._samples if s.name == name)

    def latest(self, name: str) -> MetricSample | None:
        return self._latest_by_name.get(name)
