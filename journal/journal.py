"""AB-45 trade-journal service."""

from __future__ import annotations

from datetime import datetime

from trading.paper.lifecycle import TradeOutcome

from .models import TradeJournalRecord
from .store import TradeJournalStore


class TradeJournal:
    """High-level append-only trade journal."""

    def __init__(
        self,
        store: TradeJournalStore,
    ) -> None:
        self.store = store

    def record_outcome(
        self,
        outcome: TradeOutcome,
    ) -> TradeJournalRecord:
        """Persist a completed TradeOutcome."""

        record = TradeJournalRecord.from_trade_outcome(
            outcome
        )

        self.store.append(record)

        return record

    def records(
        self,
    ) -> tuple[TradeJournalRecord, ...]:
        """Return all journal records."""

        return self.store.read_all()

    def by_symbol(
        self,
        symbol: str,
    ) -> tuple[TradeJournalRecord, ...]:
        """Return records for one symbol."""

        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError(
                "symbol must not be empty"
            )

        return tuple(
            record
            for record in self.records()
            if record.symbol == normalized
        )

    def by_time_range(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[TradeJournalRecord, ...]:
        """Return trades whose entry occurs inside the range."""

        if start > end:
            raise ValueError(
                "start must not be after end"
            )

        return tuple(
            record
            for record in self.records()
            if start <= record.entry_time <= end
        )

    def winners(
        self,
    ) -> tuple[TradeJournalRecord, ...]:
        """Return profitable trades."""

        return tuple(
            record
            for record in self.records()
            if record.net_pnl > 0
        )

    def losers(
        self,
    ) -> tuple[TradeJournalRecord, ...]:
        """Return losing trades."""

        return tuple(
            record
            for record in self.records()
            if record.net_pnl < 0
        )
