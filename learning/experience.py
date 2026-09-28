"""Authoritative bridge from Phase-16 journal evidence to learning context.

A learning experience is valid only when a strategy decision and completed
trade outcome share the same trade_id. Future outcome values are stored as
outcomes, never copied into the decision-time feature snapshot.

References:
    Phase 16 Trade Journal / Trading Memory.
    Self-learning build order SL-0 to SL-3.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from journal.models import TradeDecisionRecord, TradeJournalRecord

from .self_learning_models import TradeOutcomeContext


class ExperienceContractError(ValueError):
    """Raised when decision/outcome evidence cannot be linked safely."""


@dataclass(frozen=True, slots=True)
class ExperienceAudit:
    """Immutable audit result for a decision/outcome population."""

    decision_count: int
    outcome_count: int
    linked_count: int
    orphan_decision_ids: tuple[str, ...]
    orphan_outcome_ids: tuple[str, ...]
    duplicate_decision_ids: tuple[str, ...]
    duplicate_outcome_ids: tuple[str, ...]
    causal_violations: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Return whether no structural or causal violation was detected."""
        return not (
            self.orphan_decision_ids
            or self.orphan_outcome_ids
            or self.duplicate_decision_ids
            or self.duplicate_outcome_ids
            or self.causal_violations
        )


def _duplicates(values: list[str]) -> tuple[str, ...]:
    """Return identifiers appearing more than once."""
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return tuple(sorted(value for value, count in counts.items() if count > 1))


def audit_journal_linkage(
    decisions: tuple[TradeDecisionRecord, ...],
    outcomes: tuple[TradeJournalRecord, ...],
) -> ExperienceAudit:
    """Audit journal linkage without modifying any record."""
    decision_ids = [item.trade_id for item in decisions]
    outcome_ids = [item.trade_id for item in outcomes]
    decision_set = set(decision_ids)
    outcome_set = set(outcome_ids)

    causal_violations: list[str] = []
    decision_map = {item.trade_id: item for item in decisions}

    for outcome in outcomes:
        decision = decision_map.get(outcome.trade_id)
        if decision is None:
            continue

        if outcome.entry_time < decision.timestamp:
            causal_violations.append(
                f"{outcome.trade_id}: outcome entry precedes decision timestamp"
            )
        if decision.symbol != outcome.symbol:
            causal_violations.append(f"{outcome.trade_id}: symbol mismatch")
        if decision.direction != outcome.direction:
            causal_violations.append(f"{outcome.trade_id}: direction mismatch")

    return ExperienceAudit(
        decision_count=len(decisions),
        outcome_count=len(outcomes),
        linked_count=len(decision_set & outcome_set),
        orphan_decision_ids=tuple(sorted(decision_set - outcome_set)),
        orphan_outcome_ids=tuple(sorted(outcome_set - decision_set)),
        duplicate_decision_ids=_duplicates(decision_ids),
        duplicate_outcome_ids=_duplicates(outcome_ids),
        causal_violations=tuple(sorted(set(causal_violations))),
    )


def _planned_risk(
    decision: TradeDecisionRecord,
    quantity: float,
) -> float:
    """Calculate planned monetary risk when entry and stop are available."""
    if decision.entry is None or decision.stop is None:
        return 0.0
    risk = abs(float(decision.entry) - float(decision.stop)) * quantity
    if not isfinite(risk):
        raise ExperienceContractError("planned risk must be finite")
    return risk


def _experience_label(outcome: TradeJournalRecord) -> str:
    """Map realized direction/P&L into the existing three-class label family."""
    if outcome.net_pnl > 0 and outcome.direction == "LONG":
        return "LONG_SUCCESS"
    if outcome.net_pnl > 0 and outcome.direction == "SHORT":
        return "SHORT_SUCCESS"
    return "NO_EDGE"


def build_trade_experience(
    decision: TradeDecisionRecord,
    outcome: TradeJournalRecord,
) -> TradeOutcomeContext:
    """Create an immutable learning context from one linked trade pair."""
    if not isinstance(decision, TradeDecisionRecord):
        raise TypeError("decision must be a TradeDecisionRecord")
    if not isinstance(outcome, TradeJournalRecord):
        raise TypeError("outcome must be a TradeJournalRecord")
    if decision.trade_id != outcome.trade_id:
        raise ExperienceContractError(
            "decision and outcome must share the same trade_id"
        )

    planned_risk = _planned_risk(decision, float(outcome.quantity))
    r_multiple = (
        float(outcome.net_pnl) / planned_risk
        if planned_risk > 0
        else 0.0
    )
    if not isfinite(r_multiple):
        raise ExperienceContractError("R_multiple must be finite")

    return TradeOutcomeContext(
        trade_id=outcome.trade_id,
        decision_id=decision.trade_id,
        outcome_timestamp=outcome.exit_time.isoformat(),
        outcome_label=_experience_label(outcome),
        net_pnl=float(outcome.net_pnl),
        r_multiple=r_multiple,
        mae=float(outcome.mae),
        mfe=float(outcome.mfe),
        holding_minutes=float(outcome.holding_minutes),
        costs=float(outcome.fees),
        slippage=float(outcome.slippage_cost),
        regime=decision.market_regime,
        volatility_state=decision.provenance.get("volatility_state"),
        symbol=outcome.symbol,
        sector=decision.provenance.get("sector"),
        model_version=decision.model_version,
        strategy_version=decision.strategy_version,
        risk_version=decision.risk_version,
        execution_version=decision.execution_version,
        feature_schema_version=decision.provenance.get("feature_schema_version"),
        feature_snapshot=dict(decision.features),
    )
