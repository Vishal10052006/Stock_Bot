"""
Stock Bot — Core Orchestrator

Connects the Phase-1 feature, signal, strategy, and risk layers
without using the legacy Personal AI CEO/execution architecture.
"""

from collections.abc import Sequence

from features.engine import calculate_features
from risk.gate import approve_trade
from risk.models import RiskResult
from signals.engine import generate_signal
from strategies.engine import generate_strategy
from strategies.models import StrategyDecision


def analyze_market(
    symbol: str,
    prices: Sequence[float],
    timestamp: object,
) -> tuple[StrategyDecision, RiskResult, bool]:
    """
    Run the deterministic Phase-1 analysis pipeline.

    Returns:
        strategy: Normalized strategy decision.
        risk: Risk evaluation result.
        approved: Whether the decision may proceed to paper execution.
    """

    features = calculate_features(
        symbol=symbol,
        prices=prices,
        timestamp=timestamp,
    )

    signal = generate_signal(features)
    strategy = generate_strategy(signal)

    # Phase 1 uses a fixed risk result only to validate the orchestration
    # contract. A real position-sizing/risk engine will replace this later.
    risk = RiskResult(
        decision="APPROVE",
        risk_score=0.25,
        reason="Phase-1 orchestration risk placeholder.",
    )

    approved = approve_trade(strategy, risk)

    return strategy, risk, approved
