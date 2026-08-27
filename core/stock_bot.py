"""
Stock Bot — Core Orchestrator

Connects the Phase-1 market-data, feature, signal, strategy,
and risk layers without depending on a specific market-data provider.

The existing prices-based interface is retained for backward
compatibility with the Phase-1 tests.
"""

from collections.abc import Sequence

from features.engine import calculate_features
from market_data.engine import MarketDataEngine
from market_data.providers import StaticMarketDataProvider
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

    This compatibility function preserves the existing public API
    while routing the supplied prices through MarketDataEngine.

    Returns:
        strategy: Normalized strategy decision.
        risk: Risk evaluation result.
        approved: Whether the decision may proceed to paper execution.
    """

    # Use the provider abstraction even when prices are supplied directly.
    provider = StaticMarketDataProvider(prices)
    market_data = MarketDataEngine(provider)

    # Normalize raw prices into MarketPrice domain objects.
    market_prices = market_data.get_prices(
        symbol=symbol,
        timestamp=timestamp,
    )

    # Extract numeric prices for the existing feature engine.
    normalized_prices = [
        market_price.price
        for market_price in market_prices
    ]

    features = calculate_features(
        symbol=symbol,
        prices=normalized_prices,
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
