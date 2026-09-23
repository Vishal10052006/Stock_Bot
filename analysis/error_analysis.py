"""AB-46 Phase-17 observable trade error analysis.

This module answers: "where do losses concentrate?" using only causal
Phase-16 decision snapshots linked to completed TradeJournalRecord outcomes.

It surfaces measurable associations. It does not claim causality, change
strategy/risk rules, retrain models, or promote a candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Iterable, Mapping

from journal.models import TradeDecisionRecord, TradeJournalRecord


class FindingType(str, Enum):
    LOSS = "LOSS"
    WIN = "WIN"
    LARGE_MAE = "LARGE_MAE"
    LOW_MFE = "LOW_MFE"
    COST_DRAG = "COST_DRAG"


class PatternType(str, Enum):
    REGIME_LOSS_CLUSTER = "REGIME_LOSS_CLUSTER"
    LOW_RVOL_SIDEWAYS_BREAKOUT = "LOW_RVOL_SIDEWAYS_BREAKOUT"
    HIGH_CONFIDENCE_FALSE_SIGNAL = "HIGH_CONFIDENCE_FALSE_SIGNAL"
    OPENING_WINDOW_LOSS = "OPENING_WINDOW_LOSS"
    CONSECUTIVE_LOSS_STREAK = "CONSECUTIVE_LOSS_STREAK"


@dataclass(frozen=True, slots=True)
class TradeFinding:
    journal_id: str
    finding_type: FindingType
    value: float
    detail: str


@dataclass(frozen=True, slots=True)
class PatternFinding:
    """One repeated, observable condition/outcome association."""

    pattern_type: PatternType
    conditions: tuple[str, ...]
    evidence_count: int
    population_count: int
    occurrence_rate: float
    average_net_pnl: float
    total_net_pnl: float
    source_trade_ids: tuple[str, ...]
    detail: str

    def __post_init__(self) -> None:
        if self.evidence_count < 1:
            raise ValueError("evidence_count must be at least 1")
        if self.population_count < self.evidence_count:
            raise ValueError("population_count must be >= evidence_count")
        if not 0.0 <= self.occurrence_rate <= 1.0:
            raise ValueError("occurrence_rate must be between 0 and 1")
        if len(self.source_trade_ids) != self.evidence_count:
            raise ValueError("source_trade_ids count must equal evidence_count")
        if not isfinite(self.average_net_pnl) or not isfinite(self.total_net_pnl):
            raise ValueError("pattern P&L values must be finite")


@dataclass(frozen=True, slots=True)
class ErrorAnalysisConfig:
    """Deterministic thresholds for trade findings and pattern discovery."""

    large_mae_ratio: float = 0.02
    low_mfe_ratio: float = 0.01
    cost_drag_ratio: float = 0.25
    minimum_pattern_evidence: int = 3
    minimum_pattern_occurrence_rate: float = 0.50
    high_confidence_probability: float = 0.70
    low_rvol_threshold: float = 0.80
    opening_window_minutes: int = 15
    market_open_hour: int = 9
    market_open_minute: int = 15
    consecutive_loss_threshold: int = 2
    sideways_regimes: tuple[str, ...] = ("SIDEWAYS", "RANGE")

    def __post_init__(self) -> None:
        if self.large_mae_ratio < 0 or self.low_mfe_ratio < 0:
            raise ValueError("MAE/MFE ratios must not be negative")
        if not 0 <= self.cost_drag_ratio <= 1:
            raise ValueError("cost_drag_ratio must be between 0 and 1")
        if self.minimum_pattern_evidence < 1:
            raise ValueError("minimum_pattern_evidence must be at least 1")
        if not 0 <= self.minimum_pattern_occurrence_rate <= 1:
            raise ValueError("minimum_pattern_occurrence_rate must be between 0 and 1")
        if not 0 <= self.high_confidence_probability <= 1:
            raise ValueError("high_confidence_probability must be between 0 and 1")
        if self.low_rvol_threshold <= 0:
            raise ValueError("low_rvol_threshold must be positive")
        if self.opening_window_minutes < 1:
            raise ValueError("opening_window_minutes must be positive")
        if not 0 <= self.market_open_hour <= 23:
            raise ValueError("market_open_hour must be between 0 and 23")
        if not 0 <= self.market_open_minute <= 59:
            raise ValueError("market_open_minute must be between 0 and 59")
        if self.consecutive_loss_threshold < 1:
            raise ValueError("consecutive_loss_threshold must be at least 1")
        if not self.sideways_regimes:
            raise ValueError("sideways_regimes must not be empty")


@dataclass(frozen=True, slots=True)
class SymbolAnalysis:
    symbol: str
    trade_count: int
    winning_trades: int
    losing_trades: int
    net_pnl: float
    average_pnl: float
    average_holding_minutes: float
    average_mae: float
    average_mfe: float


@dataclass(frozen=True, slots=True)
class ErrorAnalysisReport:
    findings: tuple[TradeFinding, ...]
    symbol_analysis: tuple[SymbolAnalysis, ...]
    pattern_findings: tuple[PatternFinding, ...] = ()
    analyzed_trade_count: int = 0
    linked_decision_count: int = 0

    @property
    def trade_count(self) -> int:
        if self.analyzed_trade_count:
            return self.analyzed_trade_count
        return len({finding.journal_id for finding in self.findings})

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def pattern_count(self) -> int:
        return len(self.pattern_findings)


class TradeErrorAnalyzer:
    """Analyze completed outcomes and linked decision-time context."""

    def __init__(self, config: ErrorAnalysisConfig | None = None) -> None:
        self.config = config if config is not None else ErrorAnalysisConfig()

    def analyze_trade(self, record: TradeJournalRecord) -> tuple[TradeFinding, ...]:
        if not isinstance(record, TradeJournalRecord):
            raise TypeError("record must be a TradeJournalRecord")

        findings: list[TradeFinding] = []

        if record.net_pnl < 0:
            findings.append(TradeFinding(record.journal_id, FindingType.LOSS, record.net_pnl, "Trade finished with negative net P&L."))
        elif record.net_pnl > 0:
            findings.append(TradeFinding(record.journal_id, FindingType.WIN, record.net_pnl, "Trade finished with positive net P&L."))

        notional = abs(record.entry_price * record.quantity)
        if notional > 0:
            mae_ratio = abs(record.mae) / notional
            if mae_ratio >= self.config.large_mae_ratio:
                findings.append(TradeFinding(record.journal_id, FindingType.LARGE_MAE, mae_ratio, "Maximum adverse excursion exceeded the configured threshold."))

            mfe_ratio = abs(record.mfe) / notional
            if mfe_ratio <= self.config.low_mfe_ratio:
                findings.append(TradeFinding(record.journal_id, FindingType.LOW_MFE, mfe_ratio, "Maximum favorable excursion remained below the configured threshold."))

            total_cost = abs(record.fees) + abs(record.slippage_cost)
            gross_magnitude = abs(record.gross_pnl)
            if gross_magnitude > 0:
                cost_ratio = total_cost / gross_magnitude
                if cost_ratio >= self.config.cost_drag_ratio:
                    findings.append(TradeFinding(record.journal_id, FindingType.COST_DRAG, cost_ratio, "Fees and slippage represented a material fraction of gross P&L."))

        return tuple(findings)

    def analyze(
        self,
        records: Iterable[TradeJournalRecord],
        decisions: Iterable[TradeDecisionRecord] | None = None,
    ) -> ErrorAnalysisReport:
        """Analyze outcomes; pass decisions to enable Phase-17 pattern discovery."""
        record_tuple = tuple(records)
        findings = tuple(item for record in record_tuple for item in self.analyze_trade(record))
        decision_tuple = tuple(decisions or ())
        patterns = self._discover_patterns(record_tuple, decision_tuple) if decision_tuple else ()
        return ErrorAnalysisReport(
            findings=findings,
            symbol_analysis=self._symbol_analysis(record_tuple),
            pattern_findings=patterns,
            analyzed_trade_count=len(record_tuple),
            linked_decision_count=len({r.trade_id for r in decision_tuple}),
        )

    def analyze_linked(
        self,
        decisions: Iterable[TradeDecisionRecord],
        records: Iterable[TradeJournalRecord],
    ) -> ErrorAnalysisReport:
        """Analyze the exact Phase-16 decision/outcome links."""
        return self.analyze(records, decisions=decisions)

    def _discover_patterns(
        self,
        records: tuple[TradeJournalRecord, ...],
        decisions: tuple[TradeDecisionRecord, ...],
    ) -> tuple[PatternFinding, ...]:
        decisions_by_id = {item.trade_id: item for item in decisions}
        linked = [
            (record, decisions_by_id[record.trade_id])
            for record in records
            if record.trade_id in decisions_by_id
        ]
        linked.sort(key=lambda pair: (pair[0].entry_time, pair[0].journal_id))

        patterns: list[PatternFinding] = []
        patterns.extend(self._regime_patterns(linked))
        patterns.extend(self._low_rvol_sideways_breakout(linked))
        patterns.extend(self._high_confidence_patterns(linked))
        patterns.extend(self._opening_window_patterns(linked))
        patterns.extend(self._consecutive_loss_patterns(linked))
        return tuple(sorted(patterns, key=lambda p: (p.pattern_type.value, p.conditions, p.source_trade_ids)))

    def _regime_patterns(self, linked):
        result = []
        regimes = sorted({decision.market_regime for _, decision in linked if decision.market_regime})
        for regime in regimes:
            subset = [(r, d) for r, d in linked if d.market_regime == regime]
            losses = [r for r, _ in subset if r.net_pnl < 0]
            finding = self._make_pattern(
                PatternType.REGIME_LOSS_CLUSTER,
                (f"market_regime={regime}",),
                subset,
                losses,
                "Losses are concentrated in this observed market regime.",
            )
            if finding:
                result.append(finding)
        return result

    def _low_rvol_sideways_breakout(self, linked):
        subset = []
        for record, decision in linked:
            regime = (decision.market_regime or "").upper()
            features = decision.features
            rvol = self._numeric(features.get("rvol_20"))
            breakout = any(
                self._truthy(features.get(key))
                for key in ("breakout", "breakout_up", "breakout_down")
            )
            if regime in {item.upper() for item in self.config.sideways_regimes} and rvol is not None and rvol < self.config.low_rvol_threshold and breakout:
                subset.append((record, decision))
        losses = [record for record, _ in subset if record.net_pnl < 0]
        finding = self._make_pattern(
            PatternType.LOW_RVOL_SIDEWAYS_BREAKOUT,
            (
                "market_regime in {SIDEWAYS,RANGE}",
                f"rvol_20<{self.config.low_rvol_threshold:g}",
                "breakout=True",
            ),
            subset,
            losses,
            "Losses are concentrated in sideways/range, low-RVOL breakout conditions.",
        )
        return (finding,) if finding else ()

    def _high_confidence_patterns(self, linked):
        subset = [
            pair for pair in linked
            if self._numeric(pair[1].probability) is not None
            and self._numeric(pair[1].probability) >= self.config.high_confidence_probability
        ]
        losses = [record for record, _ in subset if record.net_pnl < 0]
        finding = self._make_pattern(
            PatternType.HIGH_CONFIDENCE_FALSE_SIGNAL,
            (f"probability>={self.config.high_confidence_probability:g}",),
            subset,
            losses,
            "High-confidence decisions that still finished as losses.",
        )
        return (finding,) if finding else ()

    def _opening_window_patterns(self, linked):
        subset = [
            pair for pair in linked
            if 0 <= (
                pair[0].entry_time.hour * 60
                + pair[0].entry_time.minute
                - (self.config.market_open_hour * 60 + self.config.market_open_minute)
            ) < self.config.opening_window_minutes
        ]
        losses = [record for record, _ in subset if record.net_pnl < 0]
        finding = self._make_pattern(
            PatternType.OPENING_WINDOW_LOSS,
            (f"first_{self.config.opening_window_minutes}_minutes",),
            subset,
            losses,
            "Losses are concentrated in the configured opening window.",
        )
        return (finding,) if finding else ()

    def _consecutive_loss_patterns(self, linked):
        subset = []
        losses = []
        prior_losses = 0
        threshold = self.config.consecutive_loss_threshold
        for record, decision in linked:
            if prior_losses >= threshold:
                subset.append((record, decision))
                if record.net_pnl < 0:
                    losses.append(record)
            if record.net_pnl < 0:
                prior_losses += 1
            else:
                prior_losses = 0

        finding = self._make_pattern(
            PatternType.CONSECUTIVE_LOSS_STREAK,
            (f"after_{threshold}_consecutive_losses",),
            subset,
            losses,
            "Outcomes observed after a consecutive-loss streak.",
        )
        return (finding,) if finding else ()

    def _make_pattern(self, pattern_type, conditions, population, evidence, detail):
        if len(evidence) < self.config.minimum_pattern_evidence:
            return None
        rate = len(evidence) / len(population) if population else 0.0
        if rate < self.config.minimum_pattern_occurrence_rate:
            return None
        ids = tuple(sorted(record.journal_id for record in evidence))
        return PatternFinding(
            pattern_type=pattern_type,
            conditions=tuple(conditions),
            evidence_count=len(ids),
            population_count=len(population),
            occurrence_rate=rate,
            average_net_pnl=sum(record.net_pnl for record in evidence) / len(evidence),
            total_net_pnl=sum(record.net_pnl for record in evidence),
            source_trade_ids=ids,
            detail=detail,
        )

    @staticmethod
    def _numeric(value):
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if isfinite(result) else None

    @staticmethod
    def _truthy(value) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    def _symbol_analysis(self, records):
        symbols = sorted({record.symbol for record in records})
        result = []
        for symbol in symbols:
            rows = [record for record in records if record.symbol == symbol]
            count = len(rows)
            if not count:
                continue
            result.append(
                SymbolAnalysis(
                    symbol=symbol,
                    trade_count=count,
                    winning_trades=sum(record.net_pnl > 0 for record in rows),
                    losing_trades=sum(record.net_pnl < 0 for record in rows),
                    net_pnl=sum(record.net_pnl for record in rows),
                    average_pnl=sum(record.net_pnl for record in rows) / count,
                    average_holding_minutes=sum(record.holding_minutes for record in rows) / count,
                    average_mae=sum(record.mae for record in rows) / count,
                    average_mfe=sum(record.mfe for record in rows) / count,
                )
            )
        return tuple(result)
