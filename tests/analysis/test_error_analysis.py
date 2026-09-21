import pandas as pd

from analysis import (
    ErrorAnalysisConfig,
    FindingType,
    TradeErrorAnalyzer,
)
from journal.models import TradeJournalRecord
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


def test_empty_analysis() -> None:
    analyzer = TradeErrorAnalyzer()

    report = analyzer.analyze(())

    assert report.findings == ()
    assert report.symbol_analysis == ()
    assert report.trade_count == 0
    assert report.finding_count == 0
