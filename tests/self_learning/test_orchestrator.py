"""Tests for the end-to-end evidence-learning orchestrator."""

import pandas as pd

from analysis import TradeErrorAnalyzer
from journal.models import TradeDecisionRecord, TradeJournalRecord
from self_learning.contracts import LearningTrigger
from self_learning.orchestrator import SelfLearningOrchestrator
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _pair(index: int):
    ts = pd.Timestamp("2026-09-01 09:15:00", tz="Asia/Kolkata") + pd.Timedelta(minutes=index * 10)
    outcome = TradeOutcome(
        symbol="ITC",
        direction=StrategyDirection.LONG,
        entry_time=ts,
        exit_time=ts + pd.Timedelta(minutes=5),
        entry_price=100.0,
        exit_price=96.0,
        quantity=1.0,
        gross_pnl=-4.0,
        fees=0.1,
        slippage_cost=0.1,
        net_pnl=-4.2,
        holding_minutes=5.0,
        mae=-2.0,
        mfe=0.5,
    )
    record = TradeJournalRecord.from_trade_outcome(outcome)
    decision = TradeDecisionRecord(
        trade_id=record.trade_id,
        timestamp=ts.to_pydatetime(),
        symbol="ITC",
        direction="LONG",
        market_regime="RANGE",
        features={"rvol_20": 0.6, "breakout": True},
        model_version="model-v1",
        probability=0.8,
        entry=100.0,
        stop=98.0,
        target=104.0,
        position_size=1.0,
        failure_reason=None,
        strategy_version="strategy-v1",
    )
    return record, decision


def test_evidence_cycle_is_deterministic() -> None:
    pairs = tuple(_pair(index) for index in range(4))
    records = tuple(item[0] for item in pairs)
    decisions = tuple(item[1] for item in pairs)

    # A fixed journal fingerprint is the caller-owned identity of the source.
    journal_fp = "a" * 64
    orchestrator = SelfLearningOrchestrator()

    first = orchestrator.run_evidence_cycle(
        records,
        decisions,
        journal_fingerprint=journal_fp,
        created_at="2026-09-24T10:00:00+05:30",
    )
    second = orchestrator.run_evidence_cycle(
        records,
        decisions,
        journal_fingerprint=journal_fp,
        created_at="2026-09-24T10:00:00+05:30",
    )

    assert first.cycle.fingerprint == second.cycle.fingerprint
    assert first.bundle.fingerprint == second.bundle.fingerprint
    assert tuple(item.fingerprint for item in first.evidence) == tuple(
        item.fingerprint for item in second.evidence
    )


def test_evidence_cycle_preserves_trade_identity_and_trigger() -> None:
    pairs = tuple(_pair(index) for index in range(4))
    result = SelfLearningOrchestrator().run_evidence_cycle(
        tuple(item[0] for item in pairs),
        tuple(item[1] for item in pairs),
        trigger=LearningTrigger.ERROR_PATTERN,
        journal_fingerprint="b" * 64,
        created_at="2026-09-24T10:00:00+05:30",
    )

    assert result.bundle.trade_ids
    assert all(item.trigger is LearningTrigger.ERROR_PATTERN for item in result.evidence)
    assert result.cycle.status == "EVIDENCE_READY"
