"""Phase 8 deterministic baseline strategy."""

from .baseline import evaluate, evaluate_row
from .models import (
    BaselineStrategyConfig,
    StrategyDecision,
    StrategyDirection,
)
from .validation import validate_strategy_output

__all__ = [
    "BaselineStrategyConfig",
    "StrategyDecision",
    "StrategyDirection",
    "evaluate",
    "evaluate_row",
    "validate_strategy_output",
]