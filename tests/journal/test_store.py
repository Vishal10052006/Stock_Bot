import pytest
import pandas as pd

from journal.models import TradeJournalRecord
from journal.store import (
    DuplicateJournalRecordError,
    TradeJournalStore,
)
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _record() -> TradeJournalRecord:
    outcome = TradeOutcome(
        symbol="ITC",
        direction=StrategyDirection.LONG,
        entry_time=pd.Timestamp(
            "2026-01-01 09:15:00+05:30"
        ),
        exit_time=pd.Timestamp(
            "2026-01-01 09:30:00+05:30"
        ),
        entry_price=100.0,
        exit_price=101.0,
        quantity=1.0,
        gross_pnl=1.0,
        fees=0.1,
        slippage_cost=0.1,
        net_pnl=0.8,
        holding_minutes=15.0,
        mae=-0.2,
        mfe=1.2,
    )

    return TradeJournalRecord.from_trade_outcome(
        outcome
    )


def test_store_appends_and_reads(
    tmp_path,
) -> None:
    store = TradeJournalStore(
        tmp_path / "trades.jsonl"
    )

    record = _record()

    store.append(record)

    assert store.count() == 1
    assert store.read_all() == (record,)


def test_store_rejects_duplicate_record(
    tmp_path,
) -> None:
    store = TradeJournalStore(
        tmp_path / "trades.jsonl"
    )

    record = _record()

    store.append(record)

    with pytest.raises(
        DuplicateJournalRecordError
    ):
        store.append(record)


def test_missing_store_is_empty(
    tmp_path,
) -> None:
    store = TradeJournalStore(
        tmp_path / "missing.jsonl"
    )

    assert store.read_all() == ()
    assert store.count() == 0
