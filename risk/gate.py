"""
Stock Bot — Risk Execution Gate

Allows paper-trade execution only when the risk decision is APPROVE.
"""

from risk.models import RiskResult
from strategies.models import StrategyDecision


def approve_trade(
    strategy: StrategyDecision,
    risk: RiskResult,
) -> bool:
    """Return whether a strategy decision may proceed to execution."""

    return risk.decision == "APPROVE"
