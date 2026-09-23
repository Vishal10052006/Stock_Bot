"""AB-47 evidence-based learning engine."""

from __future__ import annotations

from collections import defaultdict

from analysis.error_analysis import (
    ErrorAnalysisReport,
    FindingType,
    PatternFinding,
)
from journal.models import TradeJournalRecord

from .models import (
    LearningConfig,
    LearningExperience,
    LearningPattern,
    LearningReport,
)


class LearningEngine:
    """Convert repeated observable findings into learning experiences.

    The engine only produces evidence.

    It does not:
        - modify model parameters,
        - retrain models,
        - change strategy rules,
        - change risk controls,
        - promote models.
    """

    _PATTERN_MAP = {
        FindingType.LOSS: LearningPattern.LOSS,
        FindingType.WIN: LearningPattern.WIN,
        FindingType.LARGE_MAE: LearningPattern.LARGE_MAE,
        FindingType.LOW_MFE: LearningPattern.LOW_MFE,
        FindingType.COST_DRAG: LearningPattern.COST_DRAG,
    }

    def __init__(
        self,
        config: LearningConfig | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else LearningConfig()
        )

    def learn(
        self,
        records: tuple[TradeJournalRecord, ...],
        analysis: ErrorAnalysisReport,
    ) -> LearningReport:
        """Generate evidence-backed learning experiences."""

        if not isinstance(analysis, ErrorAnalysisReport):
            raise TypeError(
                "analysis must be an ErrorAnalysisReport"
            )

        records = tuple(records)

        record_ids = {
            record.journal_id
            for record in records
        }
        trade_ids = {
            record.trade_id
            for record in records
        }

        # Only findings belonging to the supplied population are eligible.
        findings = tuple(
            finding
            for finding in analysis.findings
            if finding.journal_id in record_ids
        )

        population_by_symbol: dict[
            str | None,
            int,
        ] = defaultdict(int)

        for record in records:
            population_by_symbol[
                record.symbol
            ] += 1

        population_by_symbol[None] = len(records)

        evidence: dict[
            tuple[LearningPattern, str | None],
            list[str],
        ] = defaultdict(list)

        for finding in findings:
            pattern = self._PATTERN_MAP.get(
                finding.finding_type
            )

            if pattern is None:
                continue

            matching_record = next(
                (
                    record
                    for record in records
                    if record.journal_id
                    == finding.journal_id
                ),
                None,
            )

            if matching_record is None:
                continue

            # Record both symbol-specific and global evidence.
            evidence[
                (
                    pattern,
                    matching_record.symbol,
                )
            ].append(
                matching_record.journal_id
            )

            evidence[
                (
                    pattern,
                    None,
                )
            ].append(
                matching_record.journal_id
            )

        experiences: list[LearningExperience] = []

        for (
            pattern,
            symbol,
        ), trade_ids in sorted(
            evidence.items(),
            key=lambda item: (
                item[0][0].value,
                item[0][1] or "",
            ),
        ):
            unique_trade_ids = tuple(
                sorted(set(trade_ids))
            )

            population_count = population_by_symbol[
                symbol
            ]

            evidence_count = len(
                unique_trade_ids
            )

            if evidence_count < self.config.minimum_evidence:
                continue

            occurrence_rate = (
                evidence_count
                / population_count
            )

            if (
                occurrence_rate
                < self.config.minimum_occurrence_rate
            ):
                continue

            confidence = self._confidence(
                evidence_count=evidence_count,
                population_count=population_count,
                occurrence_rate=occurrence_rate,
            )

            experiences.append(
                LearningExperience(
                    pattern=pattern,
                    symbol=symbol,
                    evidence_count=evidence_count,
                    population_count=population_count,
                    occurrence_rate=occurrence_rate,
                    confidence=confidence,
                    source_trade_ids=unique_trade_ids,
                )
            )

        experiences.extend(
            self._learn_from_patterns(
                analysis.pattern_findings,
                trade_ids,
            )
        )

        return LearningReport(
            experiences=tuple(
                sorted(
                    experiences,
                    key=lambda item: (
                        item.pattern.value,
                        item.symbol or "",
                        item.source_trade_ids,
                    ),
                )
            )
        )

    def _learn_from_patterns(
        self,
        patterns: tuple[PatternFinding, ...],
        record_ids: set[str],
    ) -> list[LearningExperience]:
        """Convert Phase-17 patterns into immutable learning evidence."""

        experiences: list[LearningExperience] = []

        for pattern in patterns:
            source_ids = tuple(
                sorted(
                    trade_id
                    for trade_id in pattern.source_trade_ids
                    if trade_id in record_ids
                )
            )

            if len(source_ids) < self.config.minimum_evidence:
                continue

            if pattern.occurrence_rate < self.config.minimum_occurrence_rate:
                continue

            confidence = self._confidence(
                evidence_count=len(source_ids),
                population_count=pattern.population_count,
                occurrence_rate=pattern.occurrence_rate,
            )

            experiences.append(
                LearningExperience(
                    pattern=LearningPattern(pattern.pattern_type.value),
                    symbol=None,
                    evidence_count=len(source_ids),
                    population_count=pattern.population_count,
                    occurrence_rate=pattern.occurrence_rate,
                    confidence=confidence,
                    source_trade_ids=source_ids,
                    conditions=pattern.conditions,
                    average_net_pnl=pattern.average_net_pnl,
                    total_net_pnl=pattern.total_net_pnl,
                    detail=pattern.detail,
                )
            )

        return experiences

    @staticmethod
    def _confidence(
        *,
        evidence_count: int,
        population_count: int,
        occurrence_rate: float,
    ) -> float:
        """Calculate conservative deterministic evidence confidence.

        Confidence combines:
            - occurrence rate,
            - evidence volume.

        The evidence-volume component asymptotically approaches 1.
        """

        evidence_strength = (
            evidence_count
            / (evidence_count + 5.0)
        )

        confidence = (
            occurrence_rate
            * evidence_strength
        )

        return min(
            1.0,
            max(0.0, confidence),
        )
