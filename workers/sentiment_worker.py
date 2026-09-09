"""Deterministic sentiment-analysis worker.

The worker consumes externally supplied sentiment evidence.
It never invents sentiment, confidence, or trading signals.

Sentiment is contextual evidence only. Final trading decisions belong
to the downstream strategy/decision/risk pipeline.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from workers.base_worker import BaseWorker


class SentimentWorker(BaseWorker):
    """Adapter for validated external sentiment information."""

    name = "sentiment_worker"
    capabilities = [
        "sentiment_analysis",
        "news_analysis",
    ]

    def execute(self, task: Any) -> dict[str, Any]:
        """Return supplied sentiment evidence without inventing data.

        Supported input:

            {"sentiment": {...}}

        The worker deliberately does not convert sentiment into BUY/SELL.
        """

        sentiment = self._extract_sentiment(task)

        if sentiment is None:
            return {
                "sentiment": "UNAVAILABLE",
                "confidence": None,
                "signal": "NO_SIGNAL",
                "success": False,
                "reason": (
                    "Sentiment analysis requires validated external "
                    "news/sentiment data; none was supplied."
                ),
            }

        return {
            "sentiment": sentiment,
            "confidence": None,
            "signal": "NO_SIGNAL",
            "success": True,
            "reason": (
                "External sentiment evidence received. "
                "No trading decision was made."
            ),
        }

    @staticmethod
    def _extract_sentiment(task: Any) -> Any:
        if isinstance(task, Mapping):
            return task.get("sentiment")

        return None
