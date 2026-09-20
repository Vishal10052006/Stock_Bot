"""Research worker adapter for STOCK_BOT's existing worker architecture.

This adapter delegates to ResearchContextBuilder and never emits
BUY/SELL orders or bypasses risk/strategy layers.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Mapping

from workers.base_worker import BaseWorker
from research.integration.context import ResearchContextBuilder


class ResearchWorker(BaseWorker):
    name = "research_worker"
    capabilities = [
        "research_context",
        "event_detection",
        "sentiment_context",
        "point_in_time_research",
    ]

    def __init__(self, builder: ResearchContextBuilder | None = None) -> None:
        self.builder = builder or ResearchContextBuilder()

    def execute(self, task: Any) -> dict[str, Any]:
        if not isinstance(task, Mapping):
            return {"success": False, "signal": "NO_SIGNAL", "reason": "ResearchWorker requires a mapping task."}

        symbol = task.get("symbol")
        as_of = task.get("as_of")
        documents = task.get("documents")
        if not isinstance(symbol, str) or not isinstance(as_of, datetime) or not isinstance(documents, tuple):
            return {"success": False, "signal": "NO_SIGNAL", "reason": "symbol, timezone-aware as_of, and tuple documents are required."}

        context = self.builder.build(symbol=symbol, as_of=as_of, documents=documents)
        return {
            "success": True,
            "signal": "NO_SIGNAL",
            "context": context,
            "reason": "Research context generated; no trading decision was made.",
        }
