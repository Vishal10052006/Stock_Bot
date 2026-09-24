"""Metric primitives for M-1 through M-8 monitoring.

References:
    STOCK_BOT Phase 23 monitoring requirements.
    TRADING_SPECIFICATION.md.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import inf
from typing import Iterable, Mapping


@dataclass(slots=True)
class Counter:
    """Monotonic integer counter for operational events."""

    value: int = 0

    def inc(self, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("counter increment must be non-negative")
        self.value += amount


@dataclass(slots=True)
class MetricSeries:
    """Small in-memory series for latency/slippage-style observations."""

    values: list[float]

    def __init__(self) -> None:
        self.values = []

    def observe(self, value: float) -> None:
        self.values.append(float(value))

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> float | None:
        return None if not self.values else sum(self.values) / len(self.values)

    @property
    def minimum(self) -> float | None:
        return None if not self.values else min(self.values)

    @property
    def maximum(self) -> float | None:
        return None if not self.values else max(self.values)


class MonitoringMetrics:
    """Process-local counters and series used to build monitoring snapshots."""

    def __init__(self) -> None:
        self.counters: dict[str, Counter] = defaultdict(Counter)
        self.series: dict[str, MetricSeries] = defaultdict(MetricSeries)

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name].inc(amount)

    def observe(self, name: str, value: float) -> None:
        self.series[name].observe(value)

    def counter_value(self, name: str) -> int:
        return self.counters[name].value

    def series_stats(self, name: str) -> Mapping[str, float | int | None]:
        series = self.series[name]
        return {
            "count": series.count,
            "mean": series.mean,
            "min": series.minimum,
            "max": series.maximum,
        }

    def snapshot(self) -> Mapping[str, object]:
        return {
            "counters": {name: metric.value for name, metric in self.counters.items()},
            "series": {
                name: dict(self.series_stats(name))
                for name in self.series
            },
        }
