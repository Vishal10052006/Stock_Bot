import pandas as pd
import pytest

from analysis import TradeErrorAnalyzer
from journal.models import TradeDecisionRecord, TradeJournalRecord
from learning import ErrorClass, LearningEngine, LearningPattern
from learning.reinforcement_engine import ReinforcementEngine
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _pair(*, pnl=-10.0, minute=30, regime="SIDEWAYS", probability=0.8, rvol=0.6, breakout=True):
    ts = pd.Timestamp("2026-01-01 09:15:00+05:30") + pd.Timedelta(minutes=minute)
    outcome = TradeOutcome(
        symbol="ITC", direction=StrategyDirection.LONG,
        entry_time=ts, exit_time=ts + pd.Timedelta(minutes=5),
        entry_price=100.0, exit_price=100.0 + pnl, quantity=1.0,
        gross_pnl=pnl, fees=0.2, slippage_cost=0.2, net_pnl=pnl,
        holding_minutes=5.0, mae=-2.0, mfe=10.0 if pnl > 0 else 1.0,
    )
    record = TradeJournalRecord.from_trade_outcome(outcome)
    decision = TradeDecisionRecord(
        trade_id=record.trade_id, timestamp=ts.to_pydatetime(), symbol="ITC",
        direction="LONG", market_regime=regime,
        features={"rvol_20": rvol, "breakout": breakout},
        model_version="MODEL-v1", probability=probability,
        entry=100.0, stop=98.0, target=104.0, position_size=1.0,
        failure_reason=None, strategy_version="STRAT-v1",
    )
    return record, decision


def test_phase18_reward_uses_realized_net_pnl_and_planned_risk():
    record, decision = _pair(pnl=-4.0)
    assert LearningEngine().reward(record, decision) == -2.0


def test_phase18_reward_is_clipped():
    record, decision = _pair(pnl=-100.0)
    assert LearningEngine().reward(record, decision) == -3.0


def test_phase18_learning_consumes_actual_outcome_and_error():
    pairs = tuple(_pair(pnl=-4.0, minute=30 + i * 10) for i in range(3))
    records = tuple(r for r, _ in pairs)
    decisions = tuple(d for _, d in pairs)
    analysis = TradeErrorAnalyzer().analyze_linked(decisions, records)
    report = LearningEngine().learn(records, analysis, decisions)
    experience = next(e for e in report.experiences if e.pattern is LearningPattern.LOSS)
    assert experience.error_class is ErrorClass.OUTCOME_LOSS
    assert experience.evidence_count == 3
    assert experience.average_reward == -2.0


def test_phase18_context_pattern_becomes_learning_evidence():
    pairs = tuple(_pair(pnl=-4.0, minute=30 + i * 10) for i in range(4))
    records = tuple(r for r, _ in pairs)
    decisions = tuple(d for _, d in pairs)
    analysis = TradeErrorAnalyzer().analyze_linked(decisions, records)
    report = LearningEngine().learn(records, analysis, decisions)
    assert any(
        e.pattern is LearningPattern.LOW_RVOL_SIDEWAYS_BREAKOUT
        and e.error_class is ErrorClass.CONTEXT_LOSS_CLUSTER
        for e in report.experiences
    )


def test_phase18_reinforcement_facade_is_outcome_based():
    record, decision = _pair(pnl=-4.0)
    engine = ReinforcementEngine()
    feedback = engine.update(record, decision)
    assert feedback["trade_id"] == record.trade_id
    assert feedback["reward"] == -2.0


def test_phase18_weight_mutation_is_blocked():
    with pytest.raises(RuntimeError):
        ReinforcementEngine().update_weights({"reward": -1.0})


def test_phase18_learning_is_deterministic():
    pairs = tuple(_pair(pnl=-4.0, minute=30 + i * 10) for i in range(4))
    records = tuple(r for r, _ in pairs)
    decisions = tuple(d for _, d in pairs)
    analysis = TradeErrorAnalyzer().analyze_linked(decisions, records)
    engine = LearningEngine()
    assert engine.learn(records, analysis, decisions) == engine.learn(records, analysis, decisions)


def test_phase18_empty_population():
    analysis = TradeErrorAnalyzer().analyze_linked((), ())
    report = LearningEngine().learn((), analysis, ())
    assert report.experiences == ()
    assert report.analyzed_trade_count == 0
    assert report.rewarded_trade_count == 0
