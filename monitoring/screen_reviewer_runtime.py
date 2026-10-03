"""Continuous observation-only screen reviewer runtime."""

from __future__ import annotations

from pathlib import Path
import json
import os

import pandas as pd

from monitoring.screen_reviewer import ScreenReviewer
from screen_observer.runtime import ScreenEvent, ScreenObserverRuntime


class ScreenReviewerRuntime:
    """Watch the desktop and publish reconciliation results beside paper telemetry."""

    def __init__(
        self,
        *,
        operator_snapshot_path: Path,
        review_output_path: Path,
        interval_seconds: float = 1.0,
        max_age_seconds: float = 30.0,
        min_confidence: float = 0.70,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.operator_snapshot_path = Path(operator_snapshot_path)
        self.review_output_path = Path(review_output_path)
        self.reviewer = ScreenReviewer(
            max_age_seconds=max_age_seconds,
            min_confidence=min_confidence,
        )
        self.runtime = ScreenObserverRuntime(
            interval=pd.Timedelta(seconds=interval_seconds).to_pytimedelta(),
            on_event=self._on_event,
        )

    def start(self) -> None:
        self._write_waiting()
        self.runtime.start()

    def stop(self) -> None:
        self.runtime.stop()

    def _on_event(self, event: ScreenEvent) -> None:
        payload = self._load_operator_snapshot()
        market = payload.get("market", {})
        timestamp = market.get("decision_time") or payload.get("timestamp")
        symbol = market.get("symbol")
        benchmark = market.get("benchmark_symbol")
        if not timestamp or not symbol:
            self._write(
                {
                    "status": "WAITING_FOR_MARKET",
                    "severity": "INFO",
                    "observed_at": event.observed_at.isoformat(),
                    "decision_timestamp": None,
                    "symbol": event.context.symbol,
                    "timeframe": event.context.timeframe,
                    "confidence": event.context.confidence.overall,
                    "reasons": ["AUTHORITATIVE_MARKET_CONTEXT_UNAVAILABLE"],
                    "authority": "OBSERVATION_ONLY",
                    "event_type": event.event_type,
                    "benchmark_symbol": benchmark,
                }
            )
            return

        market_timeframe = payload.get("timeframe", "5m")
        review = self.reviewer.review(
            event.context,
            market_symbol=str(symbol),
            market_timeframe=str(market_timeframe),
            decision_timestamp=pd.Timestamp(timestamp),
        )
        output = review.as_dict()
        output["event_type"] = event.event_type
        output["benchmark_symbol"] = benchmark
        output["market_mode"] = payload.get("mode")
        output["operator_snapshot_fingerprint"] = payload.get("fingerprint")
        self._write(output)

    def _load_operator_snapshot(self) -> dict:
        try:
            value = json.loads(self.operator_snapshot_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _write_waiting(self) -> None:
        self._write(
            {
                "status": "WAITING_FOR_MARKET",
                "severity": "INFO",
                "observed_at": None,
                "decision_timestamp": None,
                "symbol": None,
                "timeframe": None,
                "confidence": 0.0,
                "reasons": ["WAITING_FOR_AUTHORITATIVE_MARKET_CONTEXT"],
                "authority": "OBSERVATION_ONLY",
            }
        )

    def _write(self, payload: dict) -> None:
        self.review_output_path.parent.mkdir(parents=True, exist_ok=True)
        payload["fingerprint"] = __import__("hashlib").sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        temporary = self.review_output_path.with_name(
            f".{self.review_output_path.name}.tmp"
        )
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.review_output_path)


__all__ = ["ScreenReviewerRuntime"]
