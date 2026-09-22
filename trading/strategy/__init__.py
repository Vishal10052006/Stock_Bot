"""Quantitative Strategy Engine public API."""

from .baseline import evaluate, evaluate_row
from .engine import StrategyEngine, StrategyTrace
from .models import (
    BaselineStrategyConfig,
    NoTradeReason,
    StrategyConfig,
    StrategyDecision,
    StrategyDirection,
    StrategyInput,
)
from .policy import expected_value
from .registry import StrategyRegistration, StrategyRegistry
from .validation import (
    validate_strategy_decision,
    validate_strategy_output,
)

__all__ = [
    "BaselineStrategyConfig",
    "NoTradeReason",
    "StrategyConfig",
    "StrategyDecision",
    "StrategyDirection",
    "StrategyEngine",
    "StrategyInput",
    "StrategyRegistration",
    "StrategyRegistry",
    "StrategyTrace",
    "evaluate",
    "evaluate_row",
    "expected_value",
    "validate_strategy_decision",
    "validate_strategy_output",
]
