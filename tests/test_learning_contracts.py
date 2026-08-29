"""
Tests for the Stock Bot learning and reliability contracts.
"""

from learning.reliability_manager import ReliabilityManager
from learning.reinforcement_engine import ReinforcementEngine


def test_reliability_manager_records_success():
    """A successful worker execution should increase reliability."""

    manager = ReliabilityManager()

    manager.update(
        "strategy_worker",
        True,
        0.8,
    )

    assert manager.get_reliability("strategy_worker") == 1.0


def test_reliability_manager_records_failure():
    """A failed worker execution should reduce reliability."""

    manager = ReliabilityManager()

    manager.update(
        "strategy_worker",
        False,
        0.8,
    )

    assert manager.get_reliability("strategy_worker") == 0.0


def test_reinforcement_engine_calculates_reward():
    """Reward calculation should use prediction and actual outcome."""

    engine = ReinforcementEngine()

    reward = engine.calculate_reward(
        predicted=0.8,
        actual=1.0,
    )

    assert reward == 0.5
