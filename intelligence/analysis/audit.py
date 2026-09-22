"""Final production-readiness audit for the Analysis Bot.

The audit is intentionally structural and downstream-neutral. It verifies
that the canonical AnalysisContext has the required causal, provenance,
versioning, quality, fundamental, and non-trading boundaries. It does not
judge profitability or trading performance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from intelligence.analysis.contracts import AnalysisContext


@dataclass(frozen=True, slots=True)
class AnalysisAuditCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class AnalysisAuditReport:
    checks: tuple[AnalysisAuditCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def audit_analysis_context(context: AnalysisContext) -> AnalysisAuditReport:
    """Audit one canonical AnalysisContext for production boundaries."""
    checks: list[AnalysisAuditCheck] = []

    checks.append(
        AnalysisAuditCheck(
            "contract_type",
            isinstance(context, AnalysisContext),
            "Context must use the canonical AnalysisContext contract.",
        )
    )
    if not isinstance(context, AnalysisContext):
        return AnalysisAuditReport(tuple(checks))

    checks.append(
        AnalysisAuditCheck(
            "timezone_aware_timestamp",
            context.timestamp.tzinfo is not None,
            "Decision timestamp must be timezone-aware.",
        )
    )
    checks.append(
        AnalysisAuditCheck(
            "symbol_normalized",
            bool(context.symbol) and context.symbol == context.symbol.upper(),
            "Symbol must be non-empty and normalized.",
        )
    )
    checks.append(
        AnalysisAuditCheck(
            "versions_present",
            all(
                isinstance(value, str) and bool(value)
                for value in (
                    context.analysis_version,
                    context.feature_version,
                    context.data_version,
                )
            ),
            "Analysis, feature and data versions must be present.",
        )
    )
    checks.append(
        AnalysisAuditCheck(
            "causal_boundary",
            context.provenance.get("causal_boundary")
            == "information_available_at_decision_timestamp",
            "Provenance must declare the causal information boundary.",
        )
    )
    checks.append(
        AnalysisAuditCheck(
            "quality_present",
            isinstance(context.quality, dict) and "completeness" in context.quality,
            "Quality metadata must expose completeness.",
        )
    )
    checks.append(
        AnalysisAuditCheck(
            "fundamental_schema",
            isinstance(context.fundamental_context, dict)
            and "available" in context.fundamental_context,
            "Fundamental context must use the deterministic analyzer schema.",
        )
    )
    checks.append(
        AnalysisAuditCheck(
            "valuation_schema",
            isinstance(context.valuation_context, dict)
            and "available" in context.valuation_context,
            "Valuation context must use the deterministic analyzer schema.",
        )
    )
    checks.append(
        AnalysisAuditCheck(
            "no_trade_authority",
            all(
                not any(token in candidate.upper() for token in ("BUY", "SELL", "ORDER"))
                for candidate in context.candidates
            ),
            "Analytical candidates must not encode trade orders.",
        )
    )
    return AnalysisAuditReport(tuple(checks))


def audit_analysis_contexts(
    contexts: Iterable[AnalysisContext],
) -> tuple[AnalysisAuditReport, ...]:
    """Audit multiple contexts independently and deterministically."""
    return tuple(audit_analysis_context(context) for context in contexts)
