import pandas as pd

from journal.models import TradeJournalRecord
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _outcome() -> TradeOutcome:
    return TradeOutcome(
        symbol="ITC",
        direction=StrategyDirection.LONG,
        entry_time=pd.Timestamp(
            "2026-01-01 09:15:00+05:30"
        ),
        exit_time=pd.Timestamp(
            "2026-01-01 09:30:00+05:30"
        ),
        entry_price=100.0,
        exit_price=102.0,
        quantity=2.0,
        gross_pnl=4.0,
        fees=0.5,
        slippage_cost=0.2,
        net_pnl=3.3,
        holding_minutes=15.0,
        mae=-0.5,
        mfe=2.5,
    )


def test_trade_outcome_maps_to_journal_record() -> None:
    record = TradeJournalRecord.from_trade_outcome(
        _outcome()
    )

    assert record.symbol == "ITC"
    assert record.direction == "LONG"
    assert record.quantity == 2.0
    assert record.net_pnl == 3.3


def test_identical_outcomes_have_deterministic_ids() -> None:
    first = TradeJournalRecord.from_trade_outcome(
        _outcome()
    )

    second = TradeJournalRecord.from_trade_outcome(
        _outcome()
    )

    assert first.journal_id == second.journal_id


def test_record_serialization_round_trip() -> None:
    record = TradeJournalRecord.from_trade_outcome(
        _outcome()
    )

    restored = TradeJournalRecord.from_dict(
        record.to_dict()
    )

    assert restored == record
