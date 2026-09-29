"""STOCK_BOT automation control plane.

The package coordinates existing trading components without acquiring
decision, risk, safety, broker, or model-promotion authority.
"""

from .contracts import AutomationMode, RunContext, RunStatus, Stage, StageEvent
from .orchestrator import AutomationOrchestrator

__all__ = [
    "AutomationMode", "RunContext", "RunStatus", "Stage",
    "StageEvent", "AutomationOrchestrator",
]
