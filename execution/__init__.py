"""Execution safety, readiness, and broker-neutral trading execution.

The legacy worker execution adapter remains available as
``execution.execution_engine.ExecutionEngine``. The production trading
boundary is exposed separately as ``execution.engine.ExecutionEngine``.
"""

from .engine import (
    BrokerAdapter,
    ExecutionEngine as TradingExecutionEngine,
    ExecutionReadiness,
    ExecutionResult,
    Fill,
    OrderRequest,
    OrderSide,
    OrderSnapshot,
    OrderStatus,
    OrderStateMachine,
    OrderType,
    PositionSnapshot,
    TimeInForce,
)
from .readiness import (
    LiveReadinessGate,
    LiveReadinessInput,
    LiveReadinessReport,
    ReadinessEvidence,
)
from .reconciliation import (
    BrokerPosition,
    BrokerReconciler,
    ReconciliationReport,
    ReconciliationStatus,
)
from .safety import (
    IndependentSafetyGate,
    SafetyBlock,
    SafetyDecision,
    SafetyState,
)
from .routing import (
    RouteDecision,
    RouteQuote,
    RoutingPolicy,
    SmartOrderRouter,
)

def build_research_readiness_evidence(*args, **kwargs):
    """Lazily import the research adapter to avoid execution import cycles."""
    from .research_readiness import build_research_readiness_evidence as _build

    return _build(*args, **kwargs)


__all__ = [
    "BrokerAdapter",
    "BrokerPosition",
    "BrokerReconciler",
    "ExecutionReadiness",
    "ExecutionResult",
    "Fill",
    "IndependentSafetyGate",
    "LiveReadinessGate",
    "LiveReadinessInput",
    "LiveReadinessReport",
    "OrderRequest",
    "OrderSide",
    "OrderSnapshot",
    "OrderStateMachine",
    "OrderStatus",
    "OrderType",
    "PositionSnapshot",
    "ReadinessEvidence",
    "RouteDecision",
    "RouteQuote",
    "RoutingPolicy",
    "SmartOrderRouter",
    "ReconciliationReport",
    "ReconciliationStatus",
    "SafetyBlock",
    "SafetyDecision",
    "SafetyState",
    "TimeInForce",
    "TradingExecutionEngine",
]