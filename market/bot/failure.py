"""Explicit Market Bot failure states; no silent fabrication."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class MarketBotFailure:
    code: str
    message: str
    recoverable: bool
    details: dict[str, Any]

class MarketBotUnavailable(RuntimeError):
    """Raised when required market state cannot be produced safely."""

class StaleMarketDataError(MarketBotUnavailable):
    """Raised when required market observations are stale."""

class InsufficientMarketDataError(MarketBotUnavailable):
    """Raised when there is not enough causal history."""
