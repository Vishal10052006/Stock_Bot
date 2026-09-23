"""AB-47 Phase-18 evidence-based learning engine.

Pipeline:
Trade -> Outcome -> Reward -> Error classification -> Pattern discovery ->
Learning experience.

No model, strategy, risk policy, or execution behavior is modified here.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite
from typing import Iterable

from analysis import ErrorAnalysisReport, FindingType, PatternType
from journal.models import TradeDecisionRecord, TradeJournalRecord

from .models import ErrorClass, LearningConfig, LearningExperience, LearningPattern, LearningReport


_FINDING_MAP = {
    FindingType.LOSS: (LearningPattern.LOSS, ErrorClass.OUTCOME_LOSS),
    FindingType.LARGE_MAE: (LearningPattern.LARGE_MAE, ErrorClass.LARGE_ADVERSE_EXCURSION),
    FindingType.LOW_MFE: (LearningPattern.LOW_MFE, ErrorClass.LOW_FAVORABLE_EXCURSION),
    FindingType.COST_DRAG: (LearningPattern.COST_DRAG, ErrorClass.EXECUTION_COST_DRAG),
    FindingType.WIN: (LearningPattern.WIN, ErrorClass.POSITIVE_OUTCOME),
}

_PATTERN_MAP = {
    PatternType.REGIME_LOSS_CLUSTER: (LearningPattern.REGIME_LOSS_CLUSTER, ErrorClass.CONTEXT_LOSS_CLUSTER),
    PatternType.LOW_RVOL_SIDEWAYS_BREAKOUT: (LearningPattern.LOW_RVOL_SIDEWAYS_BREAKOUT, ErrorClass.CONTEXT_LOSS_CLUSTER),
    PatternType.HIGH_CONFIDENCE_FALSE_SIGNAL: (LearningPattern.HIGH_CONFIDENCE_FALSE_SIGNAL, ErrorClass.HIGH_CONFIDENCE_FAILURE),
    PatternType.OPENING_WINDOW_LOSS: (LearningPattern.OPENING_WINDOW_LOSS, ErrorClass.CONTEXT_LOSS_CLUSTER),
    PatternType.CONSECUTIVE_LOSS_STREAK: (LearningPattern.CONSECUTIVE_LOSS_STREAK, ErrorClass.SEQUENCE_DETERIORATION),
}


class LearningEngine:
    """Turn real trade outcomes into deterministic learning evidence."""

    def __init__(self, config: LearningConfig | None = None) -> None:
        self.config = config if config is not None else LearningConfig()

    def reward(
        self,
        outcome: TradeJournalRecord,
        decision: TradeDecisionRecord | None = None,
    ) -> float:
        """Return normalized reward using realized net P&L.

        When decision stop/entry are available, reward is net P&L divided by
        planned monetary risk. Otherwise a conservative clipped P&L reward
        uses the outcome entry notional as the denominator.

        This is an evidence normalization, not a trading objective.
        """
        if not isinstance(outcome, TradeJournalRecord):
            raise TypeError("outcome must be a TradeJournalRecord")
        denominator = 0.0
        if decision is not None:
            if decision.entry is not None and decision.stop is not None:
                denominator = abs(decision.entry - decision.stop) * outcome.quantity
        if denominator <= 0:
            denominator = abs(outcome.entry_price * outcome.quantity)
        if denominator <= 0:
            raise ValueError("reward denominator must be positive")
        raw = outcome.net_pnl / denominator
        if not isfinite(raw):
            raise ValueError("reward must be finite")
        return max(-self.config.reward_clip, min(self.config.reward_clip, raw))

    def learn(
        self,
        records: Iterable[TradeJournalRecord],
        analysis: ErrorAnalysisReport,
        decisions: Iterable[TradeDecisionRecord] | None = None,
    ) -> LearningReport:
        """Generate evidence-backed experiences from actual trade outcomes."""
        if not isinstance(analysis, ErrorAnalysisReport):
            raise TypeError("analysis must be an ErrorAnalysisReport")

        outcomes = tuple(records)
        decision_map = {item.trade_id: item for item in tuple(decisions or ())}

        rewards = {
            record.journal_id: self.reward(record, decision_map.get(record.trade_id))
            for record in outcomes
        }

        experiences: list[LearningExperience] = []
        population = len(outcomes)

        # Per-trade classifications become learning evidence only when they
        # represent an actual outcome population and pass the evidence gates.
        finding_groups: dict[tuple[LearningPattern, str | None], set[str]] = defaultdict(set)
        finding_details: dict[tuple[LearningPattern, str | None], str] = {}

        outcome_by_journal = {record.journal_id: record for record in outcomes}

        for finding in analysis.findings:
            record = outcome_by_journal.get(finding.journal_id)
            mapped = _FINDING_MAP.get(finding.finding_type)
            if record is None or mapped is None:
                continue
            pattern, _ = mapped
            key = (pattern, record.symbol)
            finding_groups[key].add(record.journal_id)
            finding_details[key] = finding.detail

        for key, ids in sorted(finding_groups.items(), key=lambda item: (item[0][0].value, item[0][1] or "")):
            pattern, symbol = key
            self._append_experience(
                experiences=experiences,
                pattern=pattern,
                error_class=self._error_class_for_pattern(pattern),
                symbol=symbol,
                ids=ids,
                population_count=sum(record.symbol == symbol for record in outcomes),
                rewards=rewards,
                rationale=finding_details[key],
            )

        # Phase-17 contextual patterns become higher-order learning evidence.
        for finding in analysis.pattern_findings:
            mapped = _PATTERN_MAP.get(finding.pattern_type)
            if mapped is None:
                continue
            pattern, error_class = mapped
            linked_records = {
                record.journal_id: record
                for record in outcomes
                if record.journal_id in set(finding.source_trade_ids)
            }
            if not linked_records:
                continue
            symbols = {record.symbol for record in linked_records.values()}
            symbol = next(iter(symbols)) if len(symbols) == 1 else None
            self._append_experience(
                experiences=experiences,
                pattern=pattern,
                error_class=error_class,
                symbol=symbol,
                ids=set(linked_records),
                population_count=finding.population_count,
                rewards=rewards,
                rationale=finding.detail,
            )

        return LearningReport(
            experiences=tuple(experiences),
            analyzed_trade_count=len(outcomes),
            rewarded_trade_count=len(rewards),
        )

    def _append_experience(
        self,
        *,
        experiences,
        pattern,
        error_class,
        symbol,
        ids,
        population_count,
        rewards,
        rationale,
    ) -> None:
        unique_ids = tuple(sorted(ids))
        evidence_count = len(unique_ids)
        if evidence_count < self.config.minimum_evidence or population_count < evidence_count:
            return
        occurrence_rate = evidence_count / population_count if population_count else 0.0
        if occurrence_rate < self.config.minimum_occurrence_rate:
            return

        reward_values = tuple(rewards[item] for item in unique_ids if item in rewards)
        if not reward_values:
            return

        average_reward = sum(reward_values) / len(reward_values)
        if error_class not in {ErrorClass.OUTCOME_LOSS, ErrorClass.POSITIVE_OUTCOME} and average_reward > self.config.minimum_negative_reward:
            return
        if error_class is ErrorClass.OUTCOME_LOSS and average_reward >= 0:
            return
        if error_class is ErrorClass.POSITIVE_OUTCOME and average_reward <= 0:
            return

        confidence = occurrence_rate * (evidence_count / (evidence_count + 5.0))
        experiences.append(
            LearningExperience(
                pattern=pattern,
                error_class=error_class,
                symbol=symbol,
                evidence_count=evidence_count,
                population_count=population_count,
                occurrence_rate=occurrence_rate,
                confidence=min(1.0, max(0.0, confidence)),
                average_reward=average_reward,
                total_reward=sum(reward_values),
                source_trade_ids=unique_ids,
                rationale=rationale,
            )
        )

    @staticmethod
    def _error_class_for_pattern(pattern: LearningPattern) -> ErrorClass:
        for finding_pattern, (_, error_class) in _FINDING_MAP.items():
            if finding_pattern is pattern:
                return error_class
        return ErrorClass.OUTCOME_LOSS
