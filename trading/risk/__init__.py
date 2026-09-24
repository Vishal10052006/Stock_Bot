"""Trading risk package.

Phase 11 exposes deterministic contracts and risk controls only. Broker
execution remains outside this package.
"""

from .contracts import (
    RiskAction,
    RiskCheck,
    RiskPositionContext,
    RiskTransitionSizing,
    RiskPositionTransition,
    RiskReasonCode,
)
from .engine import RiskAssessment, RiskConfig, RiskEngine, RiskInput
from .gate import RiskDecision, RiskDecisionStatus, evaluate_strategy_risk
from .kill_switch import KillSwitchState
from .pipeline import evaluate_strategy_candidate_risk
from .position_sizing import PositionSizingResult, calculate_position_size
from .stop_loss import validate_stop
from .target import build_target

__all__ = [
    "KillSwitchState",
    "PositionSizingResult",
    "RiskAction",
    "RiskAssessment",
    "RiskCheck",
    "RiskConfig",
    "RiskDecision",
    "RiskDecisionStatus",
    "RiskEngine",
    "RiskInput",
    "RiskPositionContext",
    "RiskTransitionSizing",
    "RiskPositionTransition",
    "RiskReasonCode",
    "build_target",
    "calculate_position_size",
    "evaluate_strategy_candidate_risk",
    "evaluate_strategy_risk",
    "validate_stop",
]
