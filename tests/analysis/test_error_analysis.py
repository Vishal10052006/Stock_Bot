import pandas as pd
import pytest

from analysis import (
    PatternType,
    ErrorAnalysisConfig,
    FindingType,
    TradeErrorAnalyzer,
)
from journal.models import TradeDecisionRecord, TradeJournalRecord
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _record(
    *,
    symbol: str = "ITC",
    pnl: float = -10.0,
    mae: float = -5.0,
    mfe: float = 1.0,
    fees: float = 1.0,
    slippage: float = 1.0,
) -> TradeJournalRecord:
    outcome = TradeOutcome(
        symbol=symbol,
        direction=StrategyDirection.LONG,
        entry_time=pd.Timestamp(
            "2026-01-01 09:15:00+05:30"
        ),
        exit_time=pd.Timestamp(
            "2026-01-01 09:30:00+05:30"
        ),
        entry_price=100.0,
        exit_price=100.0 + pnl,
        quantity=1.0,
        gross_pnl=pnl,
        fees=fees,
        slippage_cost=slippage,
        net_pnl=pnl,
        holding_minutes=15.0,
        mae=mae,
        mfe=mfe,
    )

    return TradeJournalRecord.from_trade_outcome(
        outcome
    )


def test_loss_is_classified() -> None:
    analyzer = TradeErrorAnalyzer()

    findings = analyzer.analyze_trade(
        _record(pnl=-10.0)
    )

    assert any(
        finding.finding_type
        == FindingType.LOSS
        for finding in findings
    )


def test_win_is_classified() -> None:
    analyzer = TradeErrorAnalyzer()

    findings = analyzer.analyze_trade(
        _record(
            pnl=10.0,
            mae=-1.0,
            mfe=10.0,
            fees=0.1,
            slippage=0.1,
        )
    )

    assert any(
        finding.finding_type
        == FindingType.WIN
        for finding in findings
    )


def test_large_mae_is_detected() -> None:
    analyzer = TradeErrorAnalyzer(
        ErrorAnalysisConfig(
            large_mae_ratio=0.02,
        )
    )

    findings = analyzer.analyze_trade(
        _record(
            pnl=-10.0,
            mae=-5.0,
        )
    )

    assert any(
        finding.finding_type
        == FindingType.LARGE_MAE
        for finding in findings
    )


def test_low_mfe_is_detected() -> None:
    analyzer = TradeErrorAnalyzer(
        ErrorAnalysisConfig(
            low_mfe_ratio=0.01,
        )
    )

    findings = analyzer.analyze_trade(
        _record(
            pnl=-10.0,
            mfe=0.5,
        )
    )

    assert any(
        finding.finding_type
        == FindingType.LOW_MFE
        for finding in findings
    )


def test_cost_drag_is_detected() -> None:
    analyzer = TradeErrorAnalyzer(
        ErrorAnalysisConfig(
            cost_drag_ratio=0.25,
        )
    )

    findings = analyzer.analyze_trade(
        _record(
            pnl=10.0,
            mae=-1.0,
            mfe=10.0,
            fees=2.0,
            slippage=2.0,
        )
    )

    assert any(
        finding.finding_type
        == FindingType.COST_DRAG
        for finding in findings
    )


def test_symbol_aggregation() -> None:
    analyzer = TradeErrorAnalyzer()

    records = (
        _record(
            symbol="ITC",
            pnl=10.0,
            mae=-1.0,
            mfe=10.0,
            fees=0.1,
            slippage=0.1,
        ),
        _record(
            symbol="ITC",
            pnl=-5.0,
        ),
        _record(
            symbol="RELIANCE",
            pnl=20.0,
            mae=-1.0,
            mfe=20.0,
            fees=0.1,
            slippage=0.1,
        ),
    )

    report = analyzer.analyze(records)

    assert len(report.symbol_analysis) == 2

    itc = next(
        item
        for item in report.symbol_analysis
        if item.symbol == "ITC"
    )

    assert itc.trade_count == 2
    assert itc.winning_trades == 1
    assert itc.losing_trades == 1
    assert itc.net_pnl == 5.0


def test_analysis_is_deterministic() -> None:
    analyzer = TradeErrorAnalyzer()

    records = (
        _record(pnl=-10.0),
    )

    first = analyzer.analyze(records)
    second = analyzer.analyze(records)

    assert first == second


def _linked_pair(
    *,
    trade_id: str,
    pnl: float,
    entry_time: str,
    regime: str = "SIDEWAYS",
    probability: float = 0.80,
    rvol: float = 0.60,
    breakout: bool = True,
) -> tuple[TradeDecisionRecord, TradeJournalRecord]:
    timestamp = pd.Timestamp(entry_time)
    outcome = TradeOutcome(
        symbol="ITC",
        direction=StrategyDirection.LONG,
        entry_time=timestamp,
        exit_time=timestamp + pd.Timedelta(minutes=15),
        entry_price=100.0,
        exit_price=100.0 + pnl,
        quantity=1.0,
        gross_pnl=pnl,
        fees=0.1,
        slippage_cost=0.1,
        net_pnl=pnl,
        holding_minutes=15.0,
        mae=-1.0,
        mfe=max(pnl, 0.0),
    )
    record = TradeJournalRecord.from_trade_outcome(
        outcome,
        trade_id=trade_id,
    )
    decision = TradeDecisionRecord(
        trade_id=trade_id,
        timestamp=timestamp.to_pydatetime(),
        symbol="ITC",
        direction="LONG",
        market_regime=regime,
        features={
            "rvol_20": rvol,
            "breakout": breakout,
        },
        model_version="model-v1",
        probability=probability,
        entry=100.0,
        stop=98.0,
        target=103.0,
        position_size=1.0,
        failure_reason=None,
        strategy_version="strategy-v1",
    )
    return decision, record


def test_phase17_discovers_regime_and_conditioned_patterns() -> None:
    analyzer = TradeErrorAnalyzer(
        ErrorAnalysisConfig(
            minimum_pattern_evidence=3,
            minimum_pattern_occurrence_rate=0.75,
        )
    )
    pairs = tuple(
        _linked_pair(
            trade_id=f"T{i}",
            pnl=-10.0,
            entry_time=f"2026-01-01 09:{20 + i:02d}:00+05:30",
        )
        for i in range(3)
    )
    pairs += (
        _linked_pair(
            trade_id="T3",
            pnl=5.0,
            entry_time="2026-01-01 10:00:00+05:30",
        ),
    )

    report = analyzer.analyze_linked(
        [decision for decision, _ in pairs],
        [record for _, record in pairs],
    )

    pattern_types = {
        finding.pattern_type
        for finding in report.pattern_findings
    }

    assert PatternType.REGIME_LOSS_CLUSTER in pattern_types
    assert PatternType.LOW_RVOL_SIDEWAYS_BREAKOUT in pattern_types
    assert PatternType.HIGH_CONFIDENCE_FALSE_SIGNAL in pattern_types


def test_phase17_discovers_opening_and_post_loss_patterns() -> None:
    analyzer = TradeErrorAnalyzer(
        ErrorAnalysisConfig(
            minimum_pattern_evidence=3,
            minimum_pattern_occurrence_rate=1.0,
            consecutive_loss_threshold=2,
        )
    )
    pairs = tuple(
        _linked_pair(
            trade_id=f"O{i}",
            pnl=-10.0,
            entry_time=f"2026-01-01 09:{15 + i:02d}:00+05:30",
        )
        for i in range(3)
    )
    report = analyzer.analyze_linked(
        [decision for decision, _ in pairs],
        [record for _, record in pairs],
    )

    pattern_types = {
        finding.pattern_type
        for finding in report.pattern_findings
    }

    assert PatternType.OPENING_WINDOW_LOSS in pattern_types
    assert PatternType.CONSECUTIVE_LOSS_STREAK not in pattern_types

    post_loss_pairs = tuple(
        _linked_pair(
            trade_id=f"P{i}",
            pnl=-10.0 if i < 5 else 5.0,
            entry_time=f"2026-01-01 10:{i:02d}:00+05:30",
        )
        for i in range(6)
    )
    post_loss_analyzer = TradeErrorAnalyzer(
        ErrorAnalysisConfig(
            minimum_pattern_evidence=3,
            minimum_pattern_occurrence_rate=0.75,
            consecutive_loss_threshold=2,
        )
    )
    post_loss_report = post_loss_analyzer.analyze_linked(
        [decision for decision, _ in post_loss_pairs],
        [record for _, record in post_loss_pairs],
    )
    assert any(
        finding.pattern_type
        == PatternType.CONSECUTIVE_LOSS_STREAK
        for finding in post_loss_report.pattern_findings
    )


def test_phase17_ignores_unlinked_outcomes() -> None:
    decision, linked_record = _linked_pair(
        trade_id="LINKED",
        pnl=-10.0,
        entry_time="2026-01-01 10:00:00+05:30",
    )
    _, unlinked_record = _linked_pair(
        trade_id="UNLINKED",
        pnl=-20.0,
        entry_time="2026-01-01 10:30:00+05:30",
    )

    report = TradeErrorAnalyzer(
        ErrorAnalysisConfig(minimum_pattern_evidence=1)
    ).analyze_linked(
        [decision],
        [linked_record, unlinked_record],
    )

    assert report.analyzed_trade_count == 2
    assert report.linked_decision_count == 1
    assert all(
        "UNLINKED" not in finding.source_trade_ids
        for finding in report.pattern_findings
    )


def test_phase17_rejects_duplicate_decision_trade_ids() -> None:
    decision, record = _linked_pair(
        trade_id="DUP",
        pnl=-10.0,
        entry_time="2026-01-01 10:00:00+05:30",
    )

    analyzer = TradeErrorAnalyzer(
        ErrorAnalysisConfig(minimum_pattern_evidence=1)
    )

    with pytest.raises(ValueError, match="unique"):
        analyzer.analyze_linked(
            [decision, decision],
            [record],
        )


def test_empty_analysis() -> None:
    analyzer = TradeErrorAnalyzer()

    report = analyzer.analyze(())

    assert report.findings == ()
    assert report.symbol_analysis == ()
    assert report.trade_count == 0
    assert report.finding_count == 0
