"""Production Market Bot.

Market Bot describes causal market-wide state. It does not make trade,
strategy, risk, sizing, or execution decisions.
"""

from .contracts import MarketContext, MarketContextMetadata, MarketState
from .orchestrator import MarketBot, MarketBotConfig

__all__ = [
    "MarketBot",
    "MarketBotConfig",
    "MarketContext",
    "MarketContextMetadata",
    "MarketState",
]
