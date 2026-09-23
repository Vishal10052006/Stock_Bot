"""Phase-18 reinforcement compatibility layer.

The old generic predicted-vs-actual reinforcement formula is intentionally
removed from the trading learning path. Rewards are derived from completed
TradeJournalRecord outcomes by LearningEngine.

This compatibility class is evidence-only and cannot mutate weights.
"""

from __future__ import annotations

from journal.models import TradeDecisionRecord, TradeJournalRecord


class ReinforcementEngine:
    """Compatibility facade for outcome-based reinforcement evidence."""

    def __init__(self, learning_engine=None) -> None:
        self.learning_engine = learning_engine

    def calculate_reward(
        self,
        outcome: TradeJournalRecord,
        decision: TradeDecisionRecord | None = None,
    ) -> float:
        if self.learning_engine is None:
            from .engine import LearningEngine
            self.learning_engine = LearningEngine()
        return self.learning_engine.reward(outcome, decision)

    def generate_feedback(
        self,
        outcome: TradeJournalRecord,
        decision: TradeDecisionRecord | None = None,
    ) -> dict[str, object]:
        reward = self.calculate_reward(outcome, decision)
        return {
            "trade_id": outcome.trade_id,
            "reward": reward,
            "net_pnl": outcome.net_pnl,
            "fees": outcome.fees,
            "slippage_cost": outcome.slippage_cost,
        }

    def update(self, outcome: TradeJournalRecord, decision: TradeDecisionRecord | None = None):
        """Return evidence only; never update model weights."""
        return self.generate_feedback(outcome, decision)

    def update_weights(self, feedback):
        raise RuntimeError(
            "Phase-18 reinforcement is evidence-only; model weight mutation "
            "belongs to a separately validated promotion workflow."
        )
