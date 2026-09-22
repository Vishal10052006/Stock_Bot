"""Structural production-readiness audit for the Research Bot.

This check verifies reproducibility, chronology, provenance and accounting.
It intentionally does not declare predictive usefulness; that requires a
real historical corpus and out-of-sample evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass

from research.corpus.builder import HistoricalCorpusBuildAudit
from research.corpus.schema import HistoricalResearchCorpus


@dataclass(frozen=True, slots=True)
class ProductionCheckResult:
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "BLOCKED"


def run_production_check(
    corpus: HistoricalResearchCorpus,
    audit: HistoricalCorpusBuildAudit,
    *,
    minimum_documents: int = 1,
    required_sources: tuple[str, ...] = (),
    evaluated_oos_folds: int = 0,
) -> ProductionCheckResult:
    """Audit structural readiness without overstating empirical evidence."""
    checks: list[str] = []
    failures: list[str] = []
    warnings: list[str] = []

    if corpus.document_count >= minimum_documents:
        checks.append("historical_corpus_non_empty")
    else:
        failures.append("historical corpus is empty or below minimum_documents")

    if corpus.fingerprint and len(corpus.fingerprint) == 64:
        checks.append("corpus_fingerprint_present")
    else:
        failures.append("corpus fingerprint is missing or invalid")

    if audit.input_documents == (
        audit.accepted_documents
        + audit.duplicate_documents
        + audit.rejected_documents
    ):
        checks.append("corpus_accounting")
    else:
        failures.append("corpus accounting does not reconcile")

    source_ids = {item.document.source_id for item in corpus.documents}
    missing_sources = sorted(set(required_sources) - source_ids)
    if missing_sources:
        failures.append(f"required sources missing: {missing_sources}")
    else:
        checks.append("source_coverage")

    for item in corpus.documents:
        document = item.document
        timestamps = (
            document.published_at,
            document.observed_at,
            document.processed_at,
            document.available_at,
        )
        if any(
            timestamp.tzinfo is None or timestamp.utcoffset() is None
            for timestamp in timestamps
        ):
            failures.append(f"timezone-naive timestamp in {document.document_id}")
            break
        if not (
            document.published_at
            <= document.observed_at
            <= document.available_at
        ):
            failures.append(
                f"invalid publication/availability chronology in {document.document_id}"
            )
            break
    else:
        checks.append("point_in_time_timestamps")

    if audit.rejected_documents:
        warnings.append(
            f"{audit.rejected_documents} source records were rejected during corpus build"
        )

    if evaluated_oos_folds > 0:
        checks.append("oos_evaluation_executed")
    else:
        warnings.append("no real OOS folds have been evaluated yet")

    return ProductionCheckResult(
        passed=not failures,
        checks=tuple(checks),
        failures=tuple(failures),
        warnings=tuple(warnings),
    )
