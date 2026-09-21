import pandas as pd

from journal import TradeJournal, TradeJournalStore
from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


def _outcome(
    symbol: str,
    pnl: float,
    hour: int,
) -> TradeOutcome:
    entry = pd.Timestamp(
        f"2026-01-01 {hour:02d}:15:00+05:30"
    )

    exit_time = entry + pd.Timedelta(
        minutes=15
    )

    return TradeOutcome(
        symbol=symbol,
        direction=StrategyDirection.LONG,
        entry_time=entry,
        exit_time=exit_time,
        entry_price=100.0,
        exit_price=100.0 + pnl,
        quantity=1.0,
        gross_pnl=pnl,
        fees=0.0,
        slippage_cost=0.0,
        net_pnl=pnl,
        holding_minutes=15.0,
        mae=min(pnl, 0.0),
        mfe=max(pnl, 0.0),
    )


def test_journal_records_outcomes(
    tmp_path,
) -> None:
    journal = TradeJournal(
        TradeJournalStore(
            tmp_path / "journal.jsonl"
        )
    )

    record = journal.record_outcome(
        _outcome("ITC", 10.0, 9)
    )

    assert record.symbol == "ITC"
    assert journal.records() == (record,)


def test_journal_filters_by_symbol(
    tmp_path,
) -> None:
    journal = TradeJournal(
        TradeJournalStore(
            tmp_path / "journal.jsonl"
        )
    )

    journal.record_outcome(
        _outcome("ITC", 10.0, 9)
    )

    journal.record_outcome(
        _outcome("RELIANCE", -5.0, 10)
    )

    records = journal.by_symbol("itc")

    assert len(records) == 1
    assert records[0].symbol == "ITC"


def test_journal_separates_winners_and_losers(
    tmp_path,
) -> None:
    journal = TradeJournal(
        TradeJournalStore(
            tmp_path / "journal.jsonl"
        )
    )

    journal.record_outcome(
        _outcome("ITC", 10.0, 9)
    )

    journal.record_outcome(
        _outcome("ITC", -5.0, 10)
    )

    assert len(journal.winners()) == 1
    assert len(journal.losers()) == 1
