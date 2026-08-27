"""
Stock Bot — Trading Data Models

Defines the normalized paper-trade execution contract.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


OrderSide = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class PaperOrder:
    """Represents a validated paper-trading order."""

    symbol: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime

    def __post_init__(self):
        """Validate the paper-order contract."""

        if not self.symbol:
            raise ValueError("symbol must not be empty")

        if self.side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")

        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        if self.price <= 0:
            raise ValueError("price must be greater than zero")
