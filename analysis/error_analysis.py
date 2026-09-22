"""AB-46 observable trade-error analysis.

This module identifies measurable trade patterns from the canonical
AB-45 TradeJournalRecord.

It does not infer causal explanations and does not modify models.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from journal.models import TradeJournalRecord


class FindingType(str, Enum):
    """Observable trade-pattern classifications."""

    LOSS = "LOSS"
    WIN = "WIN"
    LARGE_MAE = "LARGE_MAE"
    LOW_MFE = "LOW_MFE"
    COST_DRAG = "COST_DRAG"


@dataclass(frozen=True, slots=True)
class TradeFinding:
    """One observable finding associated with a journal record."""

    journal_id: str
    finding_type: FindingType
    value: float
    detail: str


@dataclass(frozen=True, slots=True)
class ErrorAnalysisConfig:
    """Thresholds controlling deterministic finding generation."""

    large_mae_ratio: float = 0.02
    low_mfe_ratio: float = 0.01
    cost_drag_ratio: float = 0.25

    def __post_init__(self) -> None:
        if self.large_mae_ratio < 0:
            raise ValueError(
                "large_mae_ratio must not be negative"
            )

        if self.low_mfe_ratio < 0:
            raise ValueError(
                "low_mfe_ratio must not be negative"
            )

        if not 0 <= self.cost_drag_ratio <= 1:
            raise ValueError(
                "cost_drag_ratio must be between 0 and 1"
            )


@dataclass(frozen=True, slots=True)
class SymbolAnalysis:
    """Aggregate observable statistics for one symbol."""

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
    """Immutable AB-46 analysis result."""

    findings: tuple[TradeFinding, ...]
    symbol_analysis: tuple[SymbolAnalysis, ...]

    @property
    def trade_count(self) -> int:
        """Number of analyzed trades."""

        return len(
            {
                finding.journal_id
                for finding in self.findings
            }
        )

    @property
    def finding_count(self) -> int:
        """Number of generated findings."""

        return len(self.findings)


class TradeErrorAnalyzer:
    """Analyze observable patterns in completed trades."""

    def __init__(
        self,
        config: ErrorAnalysisConfig | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else ErrorAnalysisConfig()
        )

    def analyze_trade(
        self,
        record: TradeJournalRecord,
    ) -> tuple[TradeFinding, ...]:
        """Generate deterministic findings for one trade."""

        if not isinstance(
            record,
            TradeJournalRecord,
        ):
            raise TypeError(
                "record must be a TradeJournalRecord"
            )

        findings: list[TradeFinding] = []

        if record.net_pnl < 0:
            findings.append(
                TradeFinding(
                    journal_id=record.journal_id,
                    finding_type=FindingType.LOSS,
                    value=record.net_pnl,
                    detail="Trade finished with negative net P&L.",
                )
            )
        elif record.net_pnl > 0:
            findings.append(
                TradeFinding(
                    journal_id=record.journal_id,
                    finding_type=FindingType.WIN,
                    value=record.net_pnl,
                    detail="Trade finished with positive net P&L.",
                )
            )

        # MAE is expected to be represented as a negative excursion.
        # Normalize its magnitude before comparing with entry notional.
        notional = abs(
            record.entry_price * record.quantity
        )

        if notional > 0:
            mae_ratio = abs(record.mae) / notional

            if mae_ratio >= self.config.large_mae_ratio:
                findings.append(
                    TradeFinding(
                        journal_id=record.journal_id,
                        finding_type=FindingType.LARGE_MAE,
                        value=mae_ratio,
                        detail=(
                            "Maximum adverse excursion exceeded "
                            "the configured threshold."
                        ),
                    )
                )

            mfe_ratio = abs(record.mfe) / notional

            if mfe_ratio <= self.config.low_mfe_ratio:
                findings.append(
                    TradeFinding(
                        journal_id=record.journal_id,
                        finding_type=FindingType.LOW_MFE,
                        value=mfe_ratio,
                        detail=(
                            "Maximum favorable excursion remained "
                            "below the configured threshold."
                        ),
                    )
                )

            total_cost = (
                abs(record.fees)
                + abs(record.slippage_cost)
            )

            gross_magnitude = abs(record.gross_pnl)

            if gross_magnitude > 0:
                cost_ratio = (
                    total_cost / gross_magnitude
                )

                if (
                    cost_ratio
                    >= self.config.cost_drag_ratio
                ):
                    findings.append(
                        TradeFinding(
                            journal_id=record.journal_id,
                            finding_type=FindingType.COST_DRAG,
                            value=cost_ratio,
                            detail=(
                                "Fees and slippage represented a "
                                "material fraction of gross P&L."
                            ),
                        )
                    )

        return tuple(findings)

    def analyze(
        self,
        records: tuple[
            TradeJournalRecord,
            ...,
        ],
    ) -> ErrorAnalysisReport:
        """Analyze a collection of journal records."""

        if not isinstance(records, tuple):
            records = tuple(records)

        findings: list[TradeFinding] = []

        for record in records:
            findings.extend(
                self.analyze_trade(record)
            )

        return ErrorAnalysisReport(
            findings=tuple(findings),
            symbol_analysis=self._symbol_analysis(
                records
            ),
        )

    def _symbol_analysis(
        self,
        records: tuple[
            TradeJournalRecord,
            ...,
        ],
    ) -> tuple[SymbolAnalysis, ...]:
        """Build deterministic per-symbol aggregates."""

        symbols = sorted(
            {
                record.symbol
                for record in records
            }
        )

        result: list[SymbolAnalysis] = []

        for symbol in symbols:
            rows = [
                record
                for record in records
                if record.symbol == symbol
            ]

            count = len(rows)

            if count == 0:
                continue

            winning = sum(
                record.net_pnl > 0
                for record in rows
            )

            losing = sum(
                record.net_pnl < 0
                for record in rows
            )

            result.append(
                SymbolAnalysis(
                    symbol=symbol,
                    trade_count=count,
                    winning_trades=winning,
                    losing_trades=losing,
                    net_pnl=sum(
                        record.net_pnl
                        for record in rows
                    ),
                    average_pnl=(
                        sum(
                            record.net_pnl
                            for record in rows
                        )
                        / count
                    ),
                    average_holding_minutes=(
                        sum(
                            record.holding_minutes
                            for record in rows
                        )
                        / count
                    ),
                    average_mae=(
                        sum(
                            record.mae
                            for record in rows
                        )
                        / count
                    ),
                    average_mfe=(
                        sum(
                            record.mfe
                            for record in rows
                        )
                        / count
                    ),
                )
            )

        return tuple(result)
