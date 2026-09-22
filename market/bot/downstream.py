"""Read-only Market Bot adapters for downstream Strategy and Risk layers."""
from __future__ import annotations
from typing import Any
from .contracts import MarketContext

def market_context_for_strategy(context:MarketContext)->dict[str,Any]:
    """Expose descriptive context only; no strategy decision is made."""
    return context.to_mapping()

def market_context_for_risk(context:MarketContext)->dict[str,Any]:
    """Expose descriptive market conditions; no risk authorization is made."""
    return context.to_mapping()
