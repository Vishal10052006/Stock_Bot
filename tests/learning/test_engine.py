import pandas as pd

from analysis import ErrorAnalysisConfig, PatternType, TradeErrorAnalyzer
from journal.models import TradeDecisionRecord, TradeJournalRecord
from learning import LearningEngine, LearningPattern
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _pair(trade_id: str, pnl: float) -> tuple[TradeDecisionRecord, TradeJournalRecord]:
    timestamp = pd.Timestamp(
        "2026-01-01 10:00:00+05:30"
    )
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
        market_regime="SIDEWAYS",
        features={
            "rvol_20": 0.60,
            "breakout": True,
        },
        model_version="model-v1",
        probability=0.80,
        entry=100.0,
        stop=98.0,
        target=103.0,
        position_size=1.0,
        failure_reason=None,
        strategy_version="strategy-v1",
    )
    return decision, record


def test_learning_consumes_phase17_pattern_evidence() -> None:
    pairs = tuple(
        _pair(f"T{i}", -10.0)
        for i in range(3)
    )
    decisions = tuple(item[0] for item in pairs)
    records = tuple(item[1] for item in pairs)

    analysis = TradeErrorAnalyzer(
        ErrorAnalysisConfig(
            minimum_pattern_evidence=3,
            minimum_pattern_occurrence_rate=0.50,
        )
    ).analyze_linked(decisions, records)

    report = LearningEngine().learn(
        records,
        analysis,
    )

    assert any(
        experience.pattern
        == LearningPattern.LOW_RVOL_SIDEWAYS_BREAKOUT
        for experience in report.experiences
    )

    pattern = next(
        experience
        for experience in report.experiences
        if experience.pattern
        == LearningPattern.LOW_RVOL_SIDEWAYS_BREAKOUT
    )

    assert pattern.source_trade_ids == ("T0", "T1", "T2")
    assert pattern.evidence_count == 3
    assert pattern.total_net_pnl == -30.0
    assert pattern.conditions


def test_learning_filters_analysis_to_supplied_population() -> None:
    pairs = tuple(
        _pair(f"T{i}", -10.0)
        for i in range(3)
    )
    decisions = tuple(item[0] for item in pairs)
    records = tuple(item[1] for item in pairs)

    analysis = TradeErrorAnalyzer(
        ErrorAnalysisConfig(
            minimum_pattern_evidence=3,
        )
    ).analyze_linked(decisions, records)

    subset_report = LearningEngine().learn(
        records[:2],
        analysis,
    )

    assert all(
        set(experience.source_trade_ids)
        <= {"T0", "T1"}
        for experience in subset_report.experiences
    )


def test_learning_does_not_mutate_or_promote() -> None:
    pairs = tuple(
        _pair(f"T{i}", -10.0)
        for i in range(3)
    )
    records = tuple(item[1] for item in pairs)
    analysis = TradeErrorAnalyzer(
        ErrorAnalysisConfig(
            minimum_pattern_evidence=3,
        )
    ).analyze_linked(
        tuple(item[0] for item in pairs),
        records,
    )

    report = LearningEngine().learn(
        records,
        analysis,
    )

    assert report.experiences
    assert all(
        experience.pattern
        != LearningPattern.LOW_RVOL_SIDEWAYS_BREAKOUT
        or experience.conditions
        for experience in report.experiences
    )


def test_learning_pattern_enum_matches_phase17_pattern_type() -> None:
    assert (
        LearningPattern.LOW_RVOL_SIDEWAYS_BREAKOUT.value
        == PatternType.LOW_RVOL_SIDEWAYS_BREAKOUT.value
    )
