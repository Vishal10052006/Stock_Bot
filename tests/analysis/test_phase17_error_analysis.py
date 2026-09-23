import pandas as pd

from analysis import (
    ErrorAnalysisConfig,
    PatternType,
    TradeErrorAnalyzer,
)
from journal.models import TradeDecisionRecord, TradeJournalRecord
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _pair(
    *,
    minute: int,
    pnl: float,
    regime: str = "TREND_UP",
    probability: float = 0.60,
    rvol: float = 1.20,
    breakout: bool = False,
):
    timestamp = pd.Timestamp("2026-01-01 09:15:00+05:30") + pd.Timedelta(minutes=minute)
    outcome = TradeOutcome(
        symbol="ITC",
        direction=StrategyDirection.LONG,
        entry_time=timestamp,
        exit_time=timestamp + pd.Timedelta(minutes=5),
        entry_price=100.0,
        exit_price=100.0 + pnl,
        quantity=1.0,
        gross_pnl=pnl,
        fees=0.1,
        slippage_cost=0.1,
        net_pnl=pnl,
        holding_minutes=5.0,
        mae=-1.0,
        mfe=10.0 if pnl > 0 else 1.0,
    )
    record = TradeJournalRecord.from_trade_outcome(outcome)
    decision = TradeDecisionRecord(
        trade_id=record.trade_id,
        timestamp=timestamp.to_pydatetime(),
        symbol="ITC",
        direction="LONG",
        market_regime=regime,
        features={"rvol_20": rvol, "breakout": breakout},
        model_version="MODEL-v1.0",
        probability=probability,
        entry=100.0,
        stop=98.0,
        target=103.0,
        position_size=1.0,
        failure_reason=None,
        strategy_version="STRAT-v1.0",
    )
    return record, decision


def test_phase17_regime_loss_cluster_is_surfaced():
    pairs = tuple(_pair(minute=30 + i * 10, pnl=-10.0 if i < 3 else 10.0, regime="SIDEWAYS") for i in range(4))
    report = TradeErrorAnalyzer().analyze_linked(
        [decision for _, decision in pairs],
        [record for record, _ in pairs],
    )
    finding = next(p for p in report.pattern_findings if p.pattern_type is PatternType.REGIME_LOSS_CLUSTER and p.conditions == ("market_regime=SIDEWAYS",))
    assert finding.evidence_count == 3
    assert finding.population_count == 4
    assert finding.occurrence_rate == 0.75


def test_phase17_low_rvol_sideways_breakout_cluster_is_surfaced():
    pairs = tuple(
        _pair(minute=30 + i * 10, pnl=-10.0 if i < 3 else 10.0, regime="SIDEWAYS", rvol=0.60, breakout=True)
        for i in range(4)
    )
    report = TradeErrorAnalyzer().analyze_linked(
        [decision for _, decision in pairs],
        [record for record, _ in pairs],
    )
    finding = next(p for p in report.pattern_findings if p.pattern_type is PatternType.LOW_RVOL_SIDEWAYS_BREAKOUT)
    assert finding.evidence_count == 3
    assert finding.conditions[1] == "rvol_20<0.8"


def test_phase17_high_confidence_false_signals_are_surfaced():
    pairs = tuple(
        _pair(minute=30 + i * 10, pnl=-10.0 if i < 3 else 10.0, probability=0.80)
        for i in range(4)
    )
    report = TradeErrorAnalyzer().analyze_linked(
        [decision for _, decision in pairs],
        [record for record, _ in pairs],
    )
    finding = next(p for p in report.pattern_findings if p.pattern_type is PatternType.HIGH_CONFIDENCE_FALSE_SIGNAL)
    assert finding.evidence_count == 3
    assert finding.occurrence_rate == 0.75


def test_phase17_opening_window_losses_are_surfaced():
    pairs = tuple(
        _pair(minute=i * 5, pnl=-10.0 if i < 3 else 10.0)
        for i in range(4)
    )
    report = TradeErrorAnalyzer().analyze_linked(
        [decision for _, decision in pairs],
        [record for record, _ in pairs],
    )
    finding = next(p for p in report.pattern_findings if p.pattern_type is PatternType.OPENING_WINDOW_LOSS)
    assert finding.evidence_count == 3


def test_phase17_consecutive_loss_streak_is_surfaced():
    pairs = tuple(_pair(minute=30 + i * 10, pnl=-10.0) for i in range(5))
    report = TradeErrorAnalyzer().analyze_linked(
        [decision for _, decision in pairs],
        [record for record, _ in pairs],
    )
    finding = next(p for p in report.pattern_findings if p.pattern_type is PatternType.CONSECUTIVE_LOSS_STREAK)
    assert finding.evidence_count == 3
    assert finding.population_count == 3


def test_phase17_unlinked_outcomes_do_not_enter_pattern_analysis():
    record, decision = _pair(minute=30, pnl=-10.0)
    unrelated = TradeDecisionRecord(
        trade_id="unrelated",
        timestamp=decision.timestamp,
        symbol="ITC",
        direction="LONG",
        market_regime="SIDEWAYS",
        features={"rvol_20": 0.5, "breakout": True},
        model_version="MODEL-v1.0",
        probability=0.9,
        entry=100.0,
        stop=98.0,
        target=103.0,
        position_size=1.0,
        failure_reason=None,
        strategy_version="STRAT-v1.0",
    )
    report = TradeErrorAnalyzer().analyze_linked([unrelated], [record])
    assert report.pattern_findings == ()
    assert report.linked_decision_count == 1


def test_phase17_pattern_discovery_is_deterministic():
    pairs = tuple(_pair(minute=30 + i * 10, pnl=-10.0 if i < 3 else 10.0, regime="SIDEWAYS", rvol=0.6, breakout=True, probability=0.8) for i in range(4))
    analyzer = TradeErrorAnalyzer(ErrorAnalysisConfig())
    first = analyzer.analyze_linked([d for _, d in pairs], [r for r, _ in pairs])
    second = analyzer.analyze_linked([d for _, d in pairs], [r for r, _ in pairs])
    assert first == second
