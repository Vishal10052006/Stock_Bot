"""Deterministic portfolio-state and exposure management boundary.

Portfolio sits between Strategy and Risk. It evaluates portfolio-level
constraints but never sizes trades, authorizes execution, or contacts a broker.
"""

from portfolio.contracts import (
    PortfolioAction,
    PortfolioDecision,
    PortfolioLimits,
    PortfolioPosition,
    PortfolioSnapshot,
    TradeIntent,
)
from portfolio.manager import PortfolioManager

__all__ = [
    "PortfolioAction",
    "PortfolioDecision",
    "PortfolioLimits",
    "PortfolioManager",
    "PortfolioPosition",
    "PortfolioSnapshot",
    "TradeIntent",
]
