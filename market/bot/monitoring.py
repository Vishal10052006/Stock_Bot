"""Market Bot observability metrics."""
from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from .contracts import MarketContext

@dataclass(frozen=True, slots=True)
class MarketBotMetrics:
    success: bool
    latency_seconds: float
    timestamp: str
    benchmark: str
    availability: str
    quality: float | None
    regime: str | None
    market_version: str

def measure_context(context: MarketContext, started_at: float) -> MarketBotMetrics:
    return MarketBotMetrics(True,max(0.0,perf_counter()-started_at),context.timestamp.isoformat(),context.benchmark,context.state.availability,context.state.quality,context.state.regime,context.metadata.market_version)

def health_payload(metrics: MarketBotMetrics) -> dict[str, Any]:
    return {"component":"market_bot","success":metrics.success,"latency_seconds":metrics.latency_seconds,"timestamp":metrics.timestamp,"benchmark":metrics.benchmark,"availability":metrics.availability,"quality":metrics.quality,"regime":metrics.regime,"market_version":metrics.market_version}
