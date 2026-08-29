"""
Stock Bot - Market Data Models

Defines provider-independent contracts for normalized market data.

The rest of the system should consume these models rather than
depending directly on NSE, Yahoo Finance, broker APIs, etc.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MarketPrice:
    """Represents one normalized market price observation."""

    symbol: str
    price: float
    timestamp: datetime

    def __post_init__(self):
        """Validate the market price contract."""

        if not self.symbol:
            raise ValueError("symbol must not be empty")

        if self.price <= 0:
            raise ValueError("price must be greater than zero")
