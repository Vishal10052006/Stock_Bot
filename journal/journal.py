"""AB-45/Phase-16 high-level trading memory service."""

from __future__ import annotations

from datetime import datetime

from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDecision

from .models import TradeDecisionRecord, TradeJournalRecord
from .store import TradeJournalStore


class TradeJournal:
    """Append-only journal for decisions and completed outcomes."""

    def __init__(self, store: TradeJournalStore) -> None:
        self.store = store

    def record_decision(
        self,
        decision: StrategyDecision,
        *,
        risk_assessment: object | None = None,
        authorization: object | None = None,
        trade_id: str | None = None,
    ) -> TradeDecisionRecord:
        """Persist one complete decision snapshot, including NO_TRADE."""
        record = TradeDecisionRecord.from_strategy_decision(
            decision,
            risk_assessment=risk_assessment,
            authorization=authorization,
            trade_id=trade_id,
        )
        self.store.append(record)
        return record

    def record_outcome(
        self,
        outcome: TradeOutcome,
        *,
        trade_id: str | None = None,
    ) -> TradeJournalRecord:
        """Persist a completed trade outcome and optionally link it to a decision."""
        record = TradeJournalRecord.from_trade_outcome(
            outcome,
            trade_id=trade_id,
        )
        self.store.append(record)
        return record

    def records(self) -> tuple[TradeJournalRecord, ...]:
        """Return completed trade outcomes for learning/analysis."""
        return self.store.read_all()

    def decisions(self) -> tuple[TradeDecisionRecord, ...]:
        """Return every stored decision, including NO_TRADE."""
        return self.store.read_decisions()

    def events(self):
        """Return the immutable append-order event stream."""
        return self.store.read_events()

    def by_symbol(self, symbol: str) -> tuple[TradeJournalRecord, ...]:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return tuple(record for record in self.records() if record.symbol == normalized)

    def decisions_by_symbol(self, symbol: str) -> tuple[TradeDecisionRecord, ...]:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return tuple(record for record in self.decisions() if record.symbol == normalized)

    def by_time_range(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[TradeJournalRecord, ...]:
        if start > end:
            raise ValueError("start must not be after end")
        return tuple(record for record in self.records() if start <= record.entry_time <= end)

    def winners(self) -> tuple[TradeJournalRecord, ...]:
        return tuple(record for record in self.records() if record.net_pnl > 0)

    def losers(self) -> tuple[TradeJournalRecord, ...]:
        return tuple(record for record in self.records() if record.net_pnl < 0)

    def outcome_for_trade(self, trade_id: str) -> TradeJournalRecord | None:
        """Resolve the completed outcome linked to a decision trade_id."""
        matches = tuple(record for record in self.records() if record.trade_id == trade_id)
        if len(matches) > 1:
            raise ValueError(f"multiple outcomes found for trade_id {trade_id}")
        return matches[0] if matches else None

    def decision_for_trade(self, trade_id: str) -> TradeDecisionRecord | None:
        """Resolve the decision snapshot linked to a trade_id."""
        matches = tuple(record for record in self.decisions() if record.trade_id == trade_id)
        if len(matches) > 1:
            raise ValueError(f"multiple decisions found for trade_id {trade_id}")
        return matches[0] if matches else None
