"""Frozen initial Risk Engine paper configuration."""
from trading.risk.contracts import RiskPolicy

RISK_POLICY_V1 = RiskPolicy(
    policy_version="risk_v1.0",
    risk_per_trade=0.005,
    max_daily_loss=0.015,
    max_entries_per_day=5,
    max_open_positions=3,
    max_gross_exposure=0.75,
    max_net_exposure=0.75,
    max_leverage=1.0,
    max_symbol_exposure=0.25,
    max_sector_exposure=0.40,
    max_correlation_exposure=0.60,
    min_reward_risk=1.50,
    max_liquidity_participation=0.10,
    stale_context_seconds=300.0,
    reduce_on_high_volatility=False,
    high_volatility_risk_multiplier=1.0,
    allow_missing_liquidity=False,
    require_market_open=True,
)
