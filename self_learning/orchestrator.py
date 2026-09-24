"""End-to-end controlled self-learning orchestrator.

The orchestrator coordinates evidence generation and research governance.  It
does not place orders, change hard risk limits, or promote a model without an
explicit approval call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Callable, Iterable, Mapping

from analysis import ErrorAnalysisReport, TradeErrorAnalyzer
from journal.models import TradeDecisionRecord, TradeJournalRecord
from learning.engine import LearningEngine

from .contracts import (
    ExperienceBundle,
    LearningCycleReport,
    LearningEvidence,
    LearningTrigger,
)


@dataclass(frozen=True, slots=True)
class LearningRunResult:
    """Full evidence output from one non-deploying learning investigation."""

    cycle: LearningCycleReport
    bundle: ExperienceBundle
    evidence: tuple[LearningEvidence, ...]


class SelfLearningOrchestrator:
    """Connect the authoritative journal, analysis and learning layers."""

    VERSION = "SL-20-v1"

    def __init__(
        self,
        *,
        analyzer: TradeErrorAnalyzer | None = None,
        learner: LearningEngine | None = None,
    ) -> None:
        self.analyzer = analyzer or TradeErrorAnalyzer()
        self.learner = learner or LearningEngine()

    def run_evidence_cycle(
        self,
        records: Iterable[TradeJournalRecord],
        decisions: Iterable[TradeDecisionRecord],
        *,
        trigger: LearningTrigger = LearningTrigger.NEW_OUTCOMES,
        journal_fingerprint: str,
        created_at: str | None = None,
    ) -> LearningRunResult:
        """Build a deterministic learning evidence cycle from linked outcomes."""
        outcomes = tuple(records)
        decision_records = tuple(decisions)

        if not journal_fingerprint or len(journal_fingerprint) != 64:
            raise ValueError("journal_fingerprint must be SHA-256")

        analysis: ErrorAnalysisReport = self.analyzer.analyze_linked(
            decision_records,
            outcomes,
        )
        learning_report = self.learner.learn(
            outcomes,
            analysis,
            decision_records,
        )

        analysis_fp = _fingerprint(_analysis_payload(analysis))
        experience_fingerprints: list[str] = []
        trade_ids: set[str] = set()
        evidence_records: list[LearningEvidence] = []

        for experience in learning_report.experiences:
            fingerprint = _fingerprint({
                "pattern": experience.pattern.value,
                "error_class": experience.error_class.value,
                "source_trade_ids": list(experience.source_trade_ids),
                "conditions": list(experience.conditions),
                "evidence_count": experience.evidence_count,
                "population_count": experience.population_count,
                "occurrence_rate": experience.occurrence_rate,
                "confidence": experience.confidence,
                "average_reward": experience.average_reward,
                "average_net_pnl": experience.average_net_pnl,
                "total_net_pnl": experience.total_net_pnl,
                "rationale": experience.rationale,
                "detail": experience.detail,
            })
            experience_fingerprints.append(fingerprint)
            trade_ids.update(experience.source_trade_ids)

            evidence_id = _fingerprint({
                "experience_fingerprint": fingerprint,
                "trigger": trigger.value,
            })
            evidence_records.append(
                LearningEvidence(
                    evidence_id=evidence_id,
                    pattern=experience.pattern.value,
                    error_class=experience.error_class.value,
                    source_trade_ids=experience.source_trade_ids,
                    evidence_count=experience.evidence_count,
                    population_count=experience.population_count,
                    occurrence_rate=experience.occurrence_rate,
                    confidence=experience.confidence,
                    average_reward=experience.average_reward,
                    rationale=experience.rationale,
                    conditions=experience.conditions,
                    trigger=trigger,
                    source_experience_fingerprint=fingerprint,
                )
            )

        bundle = ExperienceBundle(
            trade_ids=tuple(sorted(trade_ids)),
            experience_fingerprints=tuple(experience_fingerprints),
            learning_fingerprints=tuple(
                evidence.fingerprint for evidence in evidence_records
            ),
            outcome_count=len(outcomes),
            linked_decision_count=len(
                {
                    item.trade_id
                    for item in decision_records
                    if item.trade_id in {record.trade_id for record in outcomes}
                }
            ),
            source_journal_fingerprint=journal_fingerprint,
            source_analysis_fingerprint=analysis_fp,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
        )

        cycle_id = _fingerprint({
            "bundle": bundle.fingerprint,
            "trigger": trigger.value,
            "version": self.VERSION,
        })

        cycle = LearningCycleReport(
            cycle_id=cycle_id,
            trigger=trigger,
            experience_fingerprint=bundle.fingerprint,
            evidence_fingerprints=tuple(
                evidence.fingerprint for evidence in evidence_records
            ),
            experiment_fingerprint=None,
            validation_fingerprints=(),
            promotion_fingerprint=None,
            status="EVIDENCE_READY",
            next_action=(
                "Create a single controlled hypothesis and frozen experiment; "
                "do not modify production configuration."
            ),
        )
        return LearningRunResult(
            cycle=cycle,
            bundle=bundle,
            evidence=tuple(evidence_records),
        )


def _analysis_payload(report: ErrorAnalysisReport) -> Mapping[str, object]:
    """Serialize only deterministic analysis observations."""
    return {
        "findings": [
            {
                "journal_id": item.journal_id,
                "finding_type": item.finding_type.value,
                "value": item.value,
                "detail": item.detail,
            }
            for item in report.findings
        ],
        "patterns": [
            {
                "pattern_type": item.pattern_type.value,
                "conditions": list(item.conditions),
                "evidence_count": item.evidence_count,
                "population_count": item.population_count,
                "occurrence_rate": item.occurrence_rate,
                "average_net_pnl": item.average_net_pnl,
                "total_net_pnl": item.total_net_pnl,
                "source_trade_ids": list(item.source_trade_ids),
                "detail": item.detail,
            }
            for item in report.pattern_findings
        ],
    }


def _fingerprint(value: Mapping[str, object]) -> str:
    """Return deterministic SHA-256 for structured learning metadata."""
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["LearningRunResult", "SelfLearningOrchestrator"]
