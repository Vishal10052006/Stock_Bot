"""Validation and audit gates for Module 7 decision explanations.

The explanation layer is observational. Validation checks the integrity of
already-produced evidence; it never creates or changes a trading decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from .decision_explanation import DecisionExplanation


_STAGE_ORDER = {
    "Market": 10,
    "Analysis": 20,
    "Prediction": 30,
    "Research": 35,
    "Screen": 40,
    "Strategy": 50,
    "Risk": 60,
    "Safety": 70,
    "Execution": 80,
}


@dataclass(frozen=True, slots=True)
class ExplanationAuditResult:
    valid: bool
    reasons: tuple[str, ...] = ()
    authority: str = "OBSERVATION_ONLY"

    @property
    def usable(self) -> bool:
        return self.valid


def audit_decision_explanation(
    explanation: DecisionExplanation,
    *,
    expected_symbol: str | None = None,
) -> ExplanationAuditResult:
    """Fail closed on structural, causal, or outcome inconsistencies."""
    if not isinstance(explanation, DecisionExplanation):
        raise TypeError("explanation must be a DecisionExplanation")

    reasons: list[str] = []

    if explanation.authority != "OBSERVATION_ONLY":
        reasons.append("EXPLANATION_AUTHORITY_INVALID")

    if expected_symbol is not None:
        symbol = expected_symbol.strip().upper()
        if symbol and explanation.symbol != symbol:
            reasons.append("EXPLANATION_SYMBOL_MISMATCH")

    previous_order = -1
    seen: set[str] = set()
    for item in explanation.items:
        if item.stage not in _STAGE_ORDER:
            reasons.append(f"EXPLANATION_UNKNOWN_STAGE:{item.stage}")
            continue
        if item.stage in seen:
            reasons.append(f"EXPLANATION_DUPLICATE_STAGE:{item.stage}")
        seen.add(item.stage)
        order = _STAGE_ORDER[item.stage]
        if order < previous_order:
            reasons.append("EXPLANATION_CAUSAL_ORDER_INVALID")
        previous_order = max(previous_order, order)

    if not explanation.outcome.strip():
        reasons.append("EXPLANATION_OUTCOME_MISSING")

    states = {
        item.stage: str(item.status).strip().upper().split(".")[-1]
        for item in explanation.items
    }

    required_stage = {
        "NO_TRADE": "Strategy",
        "RISK_REJECTED": "Risk",
        "SAFETY_BLOCKED": "Safety",
        "EXECUTION_BLOCKED": "Execution",
        "EXECUTION_REJECTED": "Execution",
        "EXECUTION_FILLED": "Execution",
        "EXECUTION_PENDING": "Execution",
        "LONG": "Strategy",
        "SHORT": "Strategy",
    }.get(explanation.outcome)
    if required_stage is not None and required_stage not in states:
        reasons.append(
            f"EXPLANATION_OUTCOME_EVIDENCE_MISSING:{required_stage}"
        )

    if states.get("Strategy") == "NO_TRADE" and explanation.outcome != "NO_TRADE":
        reasons.append("EXPLANATION_OUTCOME_STRATEGY_MISMATCH")

    if states.get("Risk") == "REJECTED" and explanation.outcome not in {
        "NO_TRADE",
        "RISK_REJECTED",
    }:
        reasons.append("EXPLANATION_OUTCOME_RISK_MISMATCH")

    if states.get("Safety") in {"BLOCKED", "REJECTED"} and explanation.outcome != "SAFETY_BLOCKED":
        reasons.append("EXPLANATION_OUTCOME_SAFETY_MISMATCH")

    execution_state = states.get("Execution")
    execution_expected = {
        "BLOCKED": "EXECUTION_BLOCKED",
        "REJECTED": "EXECUTION_REJECTED",
        "REJECTED_LOCAL": "EXECUTION_REJECTED",
        "REJECTED_BROKER": "EXECUTION_REJECTED",
        "FAILED": "EXECUTION_REJECTED",
        "FILLED": "EXECUTION_FILLED",
        "PARTIALLY_FILLED": "EXECUTION_PENDING",
        "SUBMITTED": "EXECUTION_PENDING",
        "ACKNOWLEDGED": "EXECUTION_PENDING",
        "OPEN": "EXECUTION_PENDING",
        "CANCEL_PENDING": "EXECUTION_PENDING",
    }.get(execution_state)

    # A blocked execution authorization can be a downstream consequence of a
    # Risk rejection. In that case the upstream reason remains authoritative.
    risk_rejected = states.get("Risk") == "REJECTED"
    safety_blocked = states.get("Safety") in {"BLOCKED", "REJECTED"}
    if execution_expected is not None and not (
        execution_state == "BLOCKED" and (risk_rejected or safety_blocked)
    ) and explanation.outcome != execution_expected:
        reasons.append("EXPLANATION_OUTCOME_EXECUTION_MISMATCH")

    return ExplanationAuditResult(not reasons, tuple(reasons))


__all__ = ["ExplanationAuditResult", "audit_decision_explanation"]
