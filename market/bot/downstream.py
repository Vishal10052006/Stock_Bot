"""Read-only, causally gated adapters for downstream trading layers.

Market Bot supplies descriptive context only. These adapters deliberately
require a decision timestamp and freshness bound so Strategy/Risk cannot
accidentally consume future or stale market state.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .contracts import MarketContext
from .storage import require_fresh_market_context


def market_context_for_strategy(
    context: MarketContext,
    *,
    decision_timestamp: datetime,
    max_age: timedelta,
) -> dict[str, Any]:
    """Expose fresh descriptive context to Strategy without making decisions."""
    fresh = require_fresh_market_context(
        context,
        decision_timestamp=decision_timestamp,
        max_age=max_age,
    )
    return fresh.to_mapping()


def market_context_for_risk(
    context: MarketContext,
    *,
    decision_timestamp: datetime,
    max_age: timedelta,
) -> dict[str, Any]:
    """Expose fresh descriptive context to Risk without authorizing trades."""
    fresh = require_fresh_market_context(
        context,
        decision_timestamp=decision_timestamp,
        max_age=max_age,
    )
    return fresh.to_mapping()
