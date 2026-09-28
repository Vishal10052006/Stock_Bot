"""M20.3 trace boundary for live-shadow decision observations.

The authoritative Strategy -> Risk -> ExecutionAuthorization -> Paper path
already exists in PaperDecisionLoop. This module adds an auditable, compact
trace representation around that path for shadow sessions without adding
broker authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from trading.paper.decision_loop import PaperDecisionLoop, PaperDecisionRun


@dataclass(frozen=True, slots=True)
class ShadowDecisionTrace:
    """One traceable shadow decision observation."""

    timestamp: pd.Timestamp
    symbol: str
    strategy_direction: str
    strategy_reason: str
    risk_status: str
    risk_reason: str
    authorization_status: str
    authorization_reason: str
    paper_order_status: str | None
    paper_order_id: str | None

    def to_mapping(self) -> dict[str, Any]:
        """Return a JSON-safe trace record."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "strategy_direction": self.strategy_direction,
            "strategy_reason": self.strategy_reason,
            "risk_status": self.risk_status,
            "risk_reason": self.risk_reason,
            "authorization_status": self.authorization_status,
            "authorization_reason": self.authorization_reason,
            "paper_order_status": self.paper_order_status,
            "paper_order_id": self.paper_order_id,
        }


class ShadowDecisionRecorder:
    """Run the existing paper decision authority and record every step."""

    def __init__(self, *, paper_loop: PaperDecisionLoop | None = None) -> None:
        self.paper_loop = paper_loop or PaperDecisionLoop()
        self._traces: list[ShadowDecisionTrace] = []

    def run(self, rows: pd.DataFrame) -> PaperDecisionRun:
        """Process causal decision rows and retain one trace per decision."""
        run = self.paper_loop.run(rows)

        for step in run.steps:
            order = step.order
            self._traces.append(
                ShadowDecisionTrace(
                    timestamp=pd.Timestamp(step.strategy.timestamp),
                    symbol=step.strategy.symbol,
                    strategy_direction=step.strategy.direction.value,
                    strategy_reason=step.strategy.rationale,
                    risk_status=step.risk.status.value,
                    risk_reason=step.risk.reason,
                    authorization_status=step.authorization.status.value,
                    authorization_reason=step.authorization.reason,
                    paper_order_status=(
                        order.status.value if order is not None else None
                    ),
                    paper_order_id=(
                        str(order.order_id) if order is not None else None
                    ),
                )
            )

        return run

    def traces(self) -> tuple[ShadowDecisionTrace, ...]:
        """Return an immutable snapshot of all recorded decisions."""
        return tuple(self._traces)

    def evidence(self) -> dict[str, Any]:
        """Return compact decision/rejection evidence for a shadow session."""
        traces = self._traces
        return {
            "decision_count": len(traces),
            "strategy_trade_count": sum(
                trace.strategy_direction != "NO_TRADE" for trace in traces
            ),
            "risk_approved_count": sum(
                trace.risk_status == "APPROVED" for trace in traces
            ),
            "risk_rejected_count": sum(
                trace.risk_status == "REJECTED" for trace in traces
            ),
            "paper_order_count": sum(
                trace.paper_order_status is not None for trace in traces
            ),
            "live_broker_order_submission": False,
        }
