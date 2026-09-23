"""S25 structured experiment failure analysis."""

from __future__ import annotations

from dataclasses import dataclass

from .evaluation import EvaluationReport
from .record import ExperimentRecord


@dataclass(frozen=True, slots=True)
class FailureFinding:
    """One reproducible structural finding from an experiment."""

    code: str
    category: str
    message: str


@dataclass(frozen=True, slots=True)
class FailureAnalysisReport:
    """Immutable failure-analysis output without strategy selection."""

    definition_fingerprint: str
    findings: tuple[FailureFinding, ...]
    actionable: bool

    @property
    def status(self) -> str:
        return "FINDINGS" if self.findings else "NO_STRUCTURAL_FINDINGS"


def analyze_experiment_failure(
    record: ExperimentRecord,
    *,
    evaluation: EvaluationReport | None = None,
) -> FailureAnalysisReport:
    """Identify structural failure modes and research-process gaps.

    This function does not diagnose market causes or select a replacement
    strategy. It reports only evidence available in the experiment record.
    """
    if not isinstance(record, ExperimentRecord):
        raise TypeError("record must be an ExperimentRecord")
    if evaluation is not None and not isinstance(
        evaluation,
        EvaluationReport,
    ):
        raise TypeError("evaluation must be an EvaluationReport")

    findings: list[FailureFinding] = []

    if evaluation is not None and not evaluation.valid:
        findings.append(
            FailureFinding(
                "INVALID_MEASUREMENTS",
                "measurement_integrity",
                "Evaluation reported one or more metric-integrity issues.",
            )
        )

    if record.observations == 0:
        findings.append(
            FailureFinding(
                "NO_OBSERVATIONS",
                "data",
                "Experiment contains no observations.",
            )
        )

    if not record.baseline_results:
        findings.append(
            FailureFinding(
                "MISSING_BASELINE_RESULTS",
                "experiment_execution",
                "No baseline result section was recorded.",
            )
        )

    if not record.model_results:
        findings.append(
            FailureFinding(
                "MISSING_MODEL_RESULTS",
                "experiment_execution",
                "No model result section was recorded.",
            )
        )

    if record.decision == "INCONCLUSIVE":
        findings.append(
            FailureFinding(
                "INCONCLUSIVE_RESULT",
                "evidence",
                "The experiment did not establish a KEEP or REJECT decision.",
            )
        )

    if record.limitations:
        findings.append(
            FailureFinding(
                "RECORDED_LIMITATIONS",
                "evidence",
                "The experiment explicitly records limitations that remain unresolved.",
            )
        )

    if not record.root_cause:
        findings.append(
            FailureFinding(
                "ROOT_CAUSE_NOT_RECORDED",
                "learning",
                "No root-cause statement was recorded.",
            )
        )

    if not record.lesson:
        findings.append(
            FailureFinding(
                "LESSON_NOT_RECORDED",
                "learning",
                "No explicit lesson was recorded.",
            )
        )

    return FailureAnalysisReport(
        definition_fingerprint=record.definition_fingerprint,
        findings=tuple(findings),
        actionable=bool(findings),
    )
