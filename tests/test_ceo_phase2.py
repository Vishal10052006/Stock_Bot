"""
Phase 2 tests for the CEO orchestration boundary.

CEO should:
    1. Ask DecisionEngine for a decision.
    2. Execute only when permitted.
    3. Evaluate the observed result.
    4. Apply reinforcement learning after execution.

DecisionEngine itself must remain free of learning side effects.
"""

import asyncio

from core.ceo import CEO


def test_ceo_applies_learning_after_execution(monkeypatch):
    """CEO should calculate reward from the actual execution result."""

    ceo = CEO()

    execution_result = {
        "success": True,
        "confidence": 0.9,
        "worker": "strategy_worker",
    }

    execution_calls = []
    reward_calls = []
    feedback_calls = []
    weight_update_calls = []

    # Replace decision-making with a deterministic approved decision.
    monkeypatch.setattr(
        ceo.decision_engine,
        "make_decision",
        lambda **kwargs: {
            "worker": "strategy_worker",
            "decision": "EXECUTE",
            "confidence": 0.8,
            "risk": "low",
            "factors": {
                "trust": 0.5,
                "risk": 0.8,
                "time": 0.7,
                "skill": 0.7,
                "goal": 0.9,
            },
            "reason": "Test decision",
        },
    )

    async def fake_execution(command, worker_name):
        """Record execution and return an observed result."""
        execution_calls.append((command, worker_name))
        return execution_result

    monkeypatch.setattr(
        ceo.execution_engine,
        "run",
        fake_execution,
    )

    def fake_reward(predicted, actual):
        """Record the prediction-vs-observed outcome comparison."""
        reward_calls.append((predicted, actual))
        return 0.5

    def fake_feedback(factors, reward):
        """Record reinforcement feedback generation."""
        feedback_calls.append((factors, reward))
        return {"trust": 0.25}

    def fake_weight_update(feedback):
        """Record adaptive-weight updates."""
        weight_update_calls.append(feedback)

    monkeypatch.setattr(
        ceo.reinforcement_engine,
        "calculate_reward",
        fake_reward,
    )

    monkeypatch.setattr(
        ceo.reinforcement_engine,
        "generate_feedback",
        fake_feedback,
    )

    monkeypatch.setattr(
        ceo.weight_manager,
        "update_weights",
        fake_weight_update,
    )

    result = asyncio.run(ceo.act("Analyze stock"))

    # Execution must happen exactly once.
    assert execution_calls == [
        ("Analyze stock", "strategy_worker")
    ]

    # The observed execution result must be returned unchanged.
    assert result == execution_result

    # Learning must use the decision prediction and observed result.
    assert reward_calls == [(0.8, 0.9)]

    # Feedback must use the actual decision factors.
    assert feedback_calls == [
        (
            {
                "trust": 0.5,
                "risk": 0.8,
                "time": 0.7,
                "skill": 0.7,
                "goal": 0.9,
            },
            0.5,
        )
    ]

    # Weight updates must happen only after reward/feedback generation.
    assert weight_update_calls == [
        {"trust": 0.25}
    ]
