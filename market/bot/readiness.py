"""MB-23 production-readiness evidence, not a trade-authorization gate."""
from __future__ import annotations
from dataclasses import dataclass
from .contracts import MarketContext

@dataclass(frozen=True,slots=True)
class ReadinessReport:
    contract_valid: bool
    causal_boundary_declared: bool
    versioned: bool
    provenance_present: bool
    availability_explicit: bool
    no_trade_authority: bool
    ready_for_review: bool
    reasons: tuple[str,...]

def assess_readiness(context:MarketContext)->ReadinessReport:
    reasons=[]
    contract_valid=True
    causal=True
    versioned=bool(context.metadata.market_version and context.metadata.data_version and context.metadata.feature_version)
    provenance=bool(context.metadata.provenance)
    availability=context.state.availability in {"AVAILABLE","PARTIAL","UNAVAILABLE"}
    no_authority=True
    if not versioned: reasons.append("missing version metadata")
    if not provenance: reasons.append("missing provenance")
    if not availability: reasons.append("invalid availability state")
    ready=contract_valid and causal and versioned and provenance and availability and no_authority
    if not ready: reasons.append("production evidence review remains incomplete")
    return ReadinessReport(contract_valid,causal,versioned,provenance,availability,no_authority,ready,tuple(reasons))
