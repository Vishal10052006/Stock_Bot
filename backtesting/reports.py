"""Backtest report construction and JSON-safe serialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

from .engine import BacktestResult
from .metrics import BacktestMetrics, calculate_metrics


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """Immutable audit/report artifact for one historical replay."""

    metrics: BacktestMetrics
    step_count: int
    order_count: int
    completed_trade_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe report dictionary."""
        data = asdict(self.metrics)
        data.update(
            {
                "step_count": self.step_count,
                "order_count": self.order_count,
                "completed_trade_count": self.completed_trade_count,
            }
        )

        return {
            key: self._json_safe(value)
            for key, value in data.items()
        }

    @staticmethod
    def _json_safe(value: Any) -> Any:
        """Convert non-finite floating-point values to null-compatible None."""
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, dict):
            return {
                key: BacktestReport._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [
                BacktestReport._json_safe(item)
                for item in value
            ]
        return value


def build_report(
    result: BacktestResult,
) -> BacktestReport:
    """Build one deterministic report from a completed backtest."""
    if not isinstance(result, BacktestResult):
        raise TypeError("result must be a BacktestResult")

    metrics = calculate_metrics(result.outcomes)

    return BacktestReport(
        metrics=metrics,
        step_count=len(result.steps),
        order_count=len(result.orders),
        completed_trade_count=result.completed_trades,
    )
