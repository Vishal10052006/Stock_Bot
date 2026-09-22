"""MB-19/MB-20 boundary contracts."""
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class MarketPredictionInput:
    market_context:object; analysis_context:object
@dataclass(frozen=True,slots=True)
class StrategyRiskInput:
    market_context:object; analysis_context:object; prediction_context:object
def to_prediction_input(market_context,analysis_context): return MarketPredictionInput(market_context,analysis_context)
def to_strategy_risk_input(market_context,analysis_context,prediction_context): return StrategyRiskInput(market_context,analysis_context,prediction_context)
def assert_no_trade_authority(obj):
    for name in ("order","execute","position_size","buy","sell","risk_approved"):
        if hasattr(obj,name): raise TypeError(f"Market Bot contract must not expose {name}")
