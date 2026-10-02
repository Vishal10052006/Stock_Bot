"""Live Research Bot runtime adapters.

The live layer owns provider polling and an in-memory causal evidence cache.
It does not create trading decisions.
"""

from research.live.runtime import LiveResearchCache, LiveResearchRuntime

__all__ = ["LiveResearchCache", "LiveResearchRuntime"]
