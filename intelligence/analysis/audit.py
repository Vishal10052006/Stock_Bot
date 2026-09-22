"""Final production-readiness audit for the Analysis Bot.

The audit is intentionally structural and downstream-neutral. It verifies
that the canonical AnalysisContext has the required causal, provenance,
versioning, quality, fundamental, and non-trading boundaries. It does not
judge profitability or trading performance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

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


def audit_analysis_chain(
    context: AnalysisContext,
    *,
    prediction: object | None = None,
    strategy: object | None = None,
    risk: object | None = None,
) -> AnalysisAuditReport:
    """Audit the causal Analysis -> Prediction -> Strategy -> Risk seam.

    This check validates interface identity, timestamp/symbol propagation and
    causal context timestamps. It does not evaluate model quality or trading
    profitability.
    """
    checks = list(audit_analysis_context(context).checks)
    if not isinstance(context, AnalysisContext):
        return AnalysisAuditReport(tuple(checks))

    research = context.research_context
    if isinstance(research, dict) and research.get("as_of") is not None:
        try:
            research_ts = pd.Timestamp(research["as_of"])
            checks.append(
                AnalysisAuditCheck(
                    "research_not_future",
                    research_ts <= context.timestamp,
                    "Research as_of must not be later than the analysis timestamp.",
                )
            )
        except (TypeError, ValueError):
            checks.append(
                AnalysisAuditCheck(
                    "research_not_future",
                    False,
                    "Research as_of must be a valid timestamp.",
                )
            )
    else:
        checks.append(
            AnalysisAuditCheck(
                "research_not_future",
                True,
                "No research timestamp is present; missing research remains missing.",
            )
        )

    fundamental_available = bool(
        isinstance(context.fundamental_context, dict)
        and context.fundamental_context.get("available")
    )
    if fundamental_available:
        try:
            available_at = pd.Timestamp(context.fundamental_context["available_at"])
            checks.append(
                AnalysisAuditCheck(
                    "fundamental_not_future",
                    available_at <= context.timestamp,
                    "Fundamental available_at must be <= decision timestamp.",
                )
            )
        except (KeyError, TypeError, ValueError):
            checks.append(
                AnalysisAuditCheck(
                    "fundamental_not_future",
                    False,
                    "Available fundamental context must expose a valid available_at.",
                )
            )
    else:
        checks.append(
            AnalysisAuditCheck(
                "fundamental_not_future",
                True,
                "No fundamental snapshot is available at this decision time.",
            )
        )

    valuation_available = bool(
        isinstance(context.valuation_context, dict)
        and context.valuation_context.get("available")
    )
    if valuation_available:
        try:
            valuation_ts = pd.Timestamp(context.valuation_context["as_of"])
            checks.append(
                AnalysisAuditCheck(
                    "valuation_not_future",
                    valuation_ts <= context.timestamp,
                    "Valuation as_of must be <= decision timestamp.",
                )
            )
        except (KeyError, TypeError, ValueError):
            checks.append(
                AnalysisAuditCheck(
                    "valuation_not_future",
                    False,
                    "Available valuation context must expose a valid as_of.",
                )
            )
    else:
        checks.append(
            AnalysisAuditCheck(
                "valuation_not_future",
                True,
                "No valuation snapshot is available at this decision time.",
            )
        )

    if prediction is None:
        checks.append(
            AnalysisAuditCheck(
                "prediction_boundary",
                True,
                "Prediction boundary not supplied; Analysis remains downstream-neutral.",
            )
        )
    else:
        checks.extend(
            (
                AnalysisAuditCheck(
                    "prediction_type",
                    type(prediction).__name__ == "PredictionContext",
                    "Prediction output must use the canonical PredictionContext.",
                ),
                AnalysisAuditCheck(
                    "prediction_timestamp",
                    getattr(prediction, "timestamp", None) == context.timestamp,
                    "Prediction timestamp must equal the Analysis decision timestamp.",
                ),
                AnalysisAuditCheck(
                    "prediction_symbol",
                    getattr(prediction, "symbol", None) == context.symbol,
                    "Prediction symbol must equal the Analysis symbol.",
                ),
                AnalysisAuditCheck(
                    "prediction_feature_version",
                    getattr(prediction, "feature_version", None) == context.feature_version,
                    "Prediction must preserve the Analysis feature version.",
                ),
                AnalysisAuditCheck(
                    "prediction_analysis_version",
                    getattr(prediction, "analysis_version", None) == context.analysis_version,
                    "Prediction must preserve the Analysis version.",
                ),
            )
        )

    if strategy is None:
        checks.append(
            AnalysisAuditCheck(
                "strategy_boundary",
                True,
                "Strategy boundary not supplied; Analysis has no strategy authority.",
            )
        )
    else:
        checks.extend(
            (
                AnalysisAuditCheck(
                    "strategy_timestamp",
                    getattr(strategy, "timestamp", None) == context.timestamp,
                    "Strategy timestamp must equal the Analysis decision timestamp.",
                ),
                AnalysisAuditCheck(
                    "strategy_symbol",
                    getattr(strategy, "symbol", None) == context.symbol,
                    "Strategy symbol must equal the Analysis symbol.",
                ),
            )
        )

    if risk is None:
        checks.append(
            AnalysisAuditCheck(
                "risk_boundary",
                True,
                "Risk boundary not supplied; Analysis has no risk authority.",
            )
        )
    else:
        checks.extend(
            (
                AnalysisAuditCheck(
                    "risk_timestamp",
                    getattr(risk, "timestamp", None) == context.timestamp,
                    "Risk timestamp must equal the Analysis decision timestamp.",
                ),
                AnalysisAuditCheck(
                    "risk_symbol",
                    getattr(risk, "symbol", None) == context.symbol,
                    "Risk symbol must equal the Analysis symbol.",
                ),
                AnalysisAuditCheck(
                    "risk_matches_strategy",
                    getattr(risk, "strategy_direction", None)
                    == getattr(strategy, "direction", None),
                    "Risk must evaluate the Strategy direction, not Analysis output.",
                )
                if strategy is not None
                else AnalysisAuditCheck(
                    "risk_matches_strategy",
                    False,
                    "Risk audit requires the Strategy decision.",
                ),
            )
        )

    return AnalysisAuditReport(tuple(checks))
