"""Deterministic validation orchestration for self-learning candidates.

This layer consumes already-produced evidence. It never invents OOS, walk-forward
or paper results, and never treats a positive backtest alone as promotion proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from experiments.evaluation import EvaluationReport
from ml.evaluation.effective_sample import EffectiveSampleDiagnostics

from .self_learning_models import ValidationEvidence


@dataclass(frozen=True, slots=True)
class ValidationBundle:
    """All validation artifacts required for promotion review."""

    integrity: bool
    leakage: bool
    oos: bool
    walk_forward: bool
    paper: bool
    reproducibility: bool
    predictive_metrics: Mapping[str, float] = field(default_factory=dict)
    trading_metrics: Mapping[str, float] = field(default_factory=dict)
    regime_metrics: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    symbol_metrics: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    date_metrics: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    effective_sample_notes: str = ""
    issues: tuple[str, ...] = ()

    def to_evidence(self) -> ValidationEvidence:
        """Convert the complete bundle into immutable governance evidence."""
        return ValidationEvidence(
            integrity_passed=self.integrity,
            leakage_passed=self.leakage,
            oos_passed=self.oos,
            walk_forward_passed=self.walk_forward,
            paper_passed=self.paper,
            predictive_metrics=self.predictive_metrics,
            trading_metrics=self.trading_metrics,
            regime_metrics=self.regime_metrics,
            symbol_metrics=self.symbol_metrics,
            date_metrics=self.date_metrics,
            effective_sample_size_notes=self.effective_sample_notes,
            issues=self.issues,
        )


@dataclass(frozen=True, slots=True)
class ValidationOrchestrator:
    """Build promotion evidence from explicit gate outputs."""

    def assemble(
        self,
        *,
        integrity_passed: bool,
        leakage_passed: bool,
        oos_passed: bool,
        walk_forward_passed: bool,
        paper_passed: bool,
        reproducibility_passed: bool,
        predictive_metrics: Mapping[str, float] | None = None,
        trading_metrics: Mapping[str, float] | None = None,
        regime_metrics: Mapping[str, Mapping[str, float]] | None = None,
        symbol_metrics: Mapping[str, Mapping[str, float]] | None = None,
        date_metrics: Mapping[str, Mapping[str, float]] | None = None,
        effective_sample_diagnostics: EffectiveSampleDiagnostics | None = None,
        structural_evaluation: EvaluationReport | None = None,
    ) -> ValidationBundle:
        """Assemble one immutable evidence bundle from explicit gate results."""
        issues: list[str] = []

        if structural_evaluation is not None:
            if not isinstance(structural_evaluation, EvaluationReport):
                raise TypeError(
                    "structural_evaluation must be an EvaluationReport"
                )
            if not structural_evaluation.valid:
                issues.extend(structural_evaluation.issues)
                integrity_passed = False

        notes = ""
        if effective_sample_diagnostics is not None:
            if not isinstance(
                effective_sample_diagnostics,
                EffectiveSampleDiagnostics,
            ):
                raise TypeError(
                    "effective_sample_diagnostics must be an EffectiveSampleDiagnostics"
                )
            notes = (
                f"observations={effective_sample_diagnostics.observations}; "
                f"unique_symbols={effective_sample_diagnostics.unique_symbols}; "
                f"unique_dates={effective_sample_diagnostics.unique_dates}; "
                f"max_per_symbol={effective_sample_diagnostics.observations_per_symbol_max}; "
                f"max_per_date={effective_sample_diagnostics.observations_per_date_max}; "
                f"overlap_warning={effective_sample_diagnostics.overlap_warning}"
            )
            if effective_sample_diagnostics.overlap_warning:
                issues.append("OVERLAPPING_LABELS_OR_DEPENDENT_TIMESTAMPS_PRESENT")

        if not reproducibility_passed:
            issues.append("REPRODUCIBILITY_GATE_FAILED")

        return ValidationBundle(
            integrity=integrity_passed,
            leakage=leakage_passed,
            oos=oos_passed,
            walk_forward=walk_forward_passed,
            paper=paper_passed,
            reproducibility=reproducibility_passed,
            predictive_metrics=predictive_metrics or {},
            trading_metrics=trading_metrics or {},
            regime_metrics=regime_metrics or {},
            symbol_metrics=symbol_metrics or {},
            date_metrics=date_metrics or {},
            effective_sample_notes=notes,
            issues=tuple(dict.fromkeys(issues)),
        )

    @staticmethod
    def review_ready(bundle: ValidationBundle) -> bool:
        """Return whether the evidence bundle is structurally ready for review."""
        if not isinstance(bundle, ValidationBundle):
            raise TypeError("bundle must be a ValidationBundle")
        return (
            bundle.integrity
            and bundle.leakage
            and bundle.oos
            and bundle.walk_forward
            and bundle.paper
            and bundle.reproducibility
            and not bundle.issues
        )
