"""MB-23 production-readiness evidence, not a trade-authorization gate."""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import MarketContext


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    contract_valid: bool
    causal_boundary_declared: bool
    versioned: bool
    provenance_present: bool
    availability_explicit: bool
    no_trade_authority: bool
    ready_for_review: bool
    reasons: tuple[str, ...]


def assess_readiness(context: MarketContext) -> ReadinessReport:
    reasons: list[str] = []

    contract_valid = (
        context.timestamp == context.state.timestamp
        and context.benchmark.strip().upper() == context.state.benchmark
    )
    causal = context.metadata.provenance.get("causal_boundary") == (
        "information_available_at_context_timestamp"
    )
    versioned = bool(
        context.metadata.market_version
        and context.metadata.data_version
        and context.metadata.feature_version
    )
    provenance = bool(context.metadata.provenance)
    availability = context.state.availability in {
        "AVAILABLE",
        "PARTIAL",
        "UNAVAILABLE",
    }

    # The MarketContext contract exposes descriptive state only; it contains
    # no order, sizing, execution, or risk-authorization fields.
    no_authority = True

    if not contract_valid:
        reasons.append("context/state contract mismatch")
    if not causal:
        reasons.append("causal boundary is not explicitly declared")
    if not versioned:
        reasons.append("missing version metadata")
    if not provenance:
        reasons.append("missing provenance")
    if not availability:
        reasons.append("invalid availability state")

    ready = all(
        (
            contract_valid,
            causal,
            versioned,
            provenance,
            availability,
            no_authority,
        )
    )
    if not ready:
        reasons.append("production evidence review remains incomplete")

    return ReadinessReport(
        contract_valid,
        causal,
        versioned,
        provenance,
        availability,
        no_authority,
        ready,
        tuple(reasons),
    )
