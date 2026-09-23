import pandas as pd
import pytest

from execution.trading_execution import ExecutionAuthorization, ExecutionAuthorizationStatus
from journal import TradeDecisionRecord, TradeJournal, TradeJournalStore
from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.strategy.models import NoTradeReason, StrategyDecision, StrategyDirection


def _decision(direction=StrategyDirection.LONG):
    return StrategyDecision(
        timestamp=pd.Timestamp("2026-09-23 09:20:00+05:30"),
        symbol="ITC",
        direction=direction,
        strategy_version="STRAT-v1.0",
        rationale="Trend and structure conditions satisfied.",
        primary_reason=(
            NoTradeReason.REGIME_NOT_ELIGIBLE
            if direction is StrategyDirection.NO_TRADE
            else None
        ),
        regime="TREND_UP",
        regime_probability=0.80,
        prediction_probability=0.73,
        prediction_model_version="MODEL-v1.2",
        features={"rvol_20": 1.4, "vwap_distance_pct": 0.8},
        provenance={"feature_lineage": "abc"},
    )


def _risk(status=RiskDecisionStatus.APPROVED):
    return RiskDecision(
        timestamp=pd.Timestamp("2026-09-23 09:20:00+05:30"),
        symbol="ITC",
        status=status,
        strategy_direction=StrategyDirection.LONG,
        reason="Candidate passed deterministic risk controls."
        if status is RiskDecisionStatus.APPROVED
        else "Risk limit rejected candidate.",
    )


class _Assessment:
    decision = _risk()
    entry_price = 100.0
    stop_price = 98.0
    target_price = 103.0
    position_size = 25.0


def _authorization():
    return ExecutionAuthorization(
        timestamp=pd.Timestamp("2026-09-23 09:20:00+05:30"),
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="authorized",
        risk_version="RISK-v1.0",
        approved_quantity=25.0,
        approved_notional=2500.0,
        risk_decision_id="risk-1",
    )


def test_phase16_decision_record_contains_required_memory_fields():
    record = TradeDecisionRecord.from_strategy_decision(
        _decision(),
        risk_assessment=_Assessment(),
        authorization=_authorization(),
    )

    assert len(record.trade_id) == 64
    assert record.symbol == "ITC"
    assert record.direction == "LONG"
    assert record.market_regime == "TREND_UP"
    assert record.features["rvol_20"] == 1.4
    assert record.model_version == "MODEL-v1.2"
    assert record.probability == 0.73
    assert record.entry == 100.0
    assert record.stop == 98.0
    assert record.target == 103.0
    assert record.position_size == 25.0


def test_phase16_no_trade_is_first_class_and_has_failure_reason():
    record = TradeDecisionRecord.from_strategy_decision(_decision(StrategyDirection.NO_TRADE))
    assert record.direction == "NO_TRADE"
    assert record.position_size == 0.0
    assert record.failure_reason == "REGIME_NOT_ELIGIBLE"


def test_phase16_store_allows_linked_decision_and_outcome(tmp_path):
    journal = TradeJournal(TradeJournalStore(tmp_path / "journal.jsonl"))
    decision = journal.record_decision(
        _decision(),
        risk_assessment=_Assessment(),
        authorization=_authorization(),
    )
    assert journal.decision_for_trade(decision.trade_id) == decision

    from trading.paper.lifecycle import TradeOutcome

    outcome = TradeOutcome(
        symbol="ITC",
        direction=StrategyDirection.LONG,
        entry_time=pd.Timestamp("2026-09-23 09:20:00+05:30"),
        exit_time=pd.Timestamp("2026-09-23 09:35:00+05:30"),
        entry_price=100.0,
        exit_price=102.0,
        quantity=25.0,
        gross_pnl=50.0,
        fees=1.0,
        slippage_cost=0.5,
        net_pnl=48.5,
        holding_minutes=15.0,
        mae=-10.0,
        mfe=60.0,
    )
    result = journal.record_outcome(outcome, trade_id=decision.trade_id)
    assert journal.outcome_for_trade(decision.trade_id) == result
    assert len(journal.events()) == 2


def test_phase16_round_trip_preserves_decision_memory(tmp_path):
    journal = TradeJournal(TradeJournalStore(tmp_path / "journal.jsonl"))
    record = journal.record_decision(_decision())
    restored = TradeJournal(TradeJournalStore(tmp_path / "journal.jsonl")).decision_for_trade(record.trade_id)
    assert restored == record


def test_phase16_rejects_non_finite_features():
    with pytest.raises(ValueError):
        TradeDecisionRecord.from_strategy_decision(
            StrategyDecision(
                timestamp=pd.Timestamp("2026-09-23 09:20:00+05:30"),
                symbol="ITC",
                direction=StrategyDirection.LONG,
                strategy_version="STRAT-v1.0",
                rationale="valid",
                features={"bad": float("inf")},
            )
        )
