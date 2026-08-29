"""
Phase 2 tests for the DecisionEngine contract.

The decision engine is responsible for selecting the most appropriate
worker and returning a deterministic decision contract.

Execution itself belongs to ExecutionEngine.
"""


from core.decision_engine import DecisionEngine


class FakeTrustManager:
    """Minimal trust manager used by the decision-engine tests."""

    def __init__(self, trust=None):
        self.trust = trust or {}

    def get_trust(self, worker_name):
        """Return configured worker trust or the neutral default."""
        return self.trust.get(worker_name, 0.5)


class FakeMemoryManager:
    """Minimal memory manager for isolated decision tests."""

    def load_memory(self):
        """Return empty memory for deterministic tests."""
        return []


class FakeLearningEngine:
    """Minimal learning engine for isolated decision tests."""

    def get_experience(self):
        """Return zero experience."""
        return 0


class FakeStrategyEngine:
    """Minimal strategy engine for isolated decision tests."""

    def create_strategy(self, task):
        """Return a simple strategy representation."""
        return {"task": task}


class FakeWeightManager:
    """Minimal weight manager for deterministic scoring."""

    def get_weights(self):
        """Return equal Phase-2 scoring weights."""
        return {
            "trust": 0.2,
            "risk": 0.2,
            "time": 0.2,
            "skill": 0.2,
            "goal": 0.2,
        }

    def update_weights(self, feedback):
        """Accept feedback without changing test state."""
        return None


class FakeReinforcementEngine:
    """Minimal reinforcement engine for decision tests."""

    def calculate_reward(self, predicted, actual):
        """Return a neutral reward."""
        return 0.5

    def generate_feedback(self, factors, reward):
        """Return neutral feedback."""
        return {}


def build_decision_engine():
    """Build a DecisionEngine with isolated test dependencies."""

    trust_manager = FakeTrustManager()
    memory_manager = FakeMemoryManager()
    learning_engine = FakeLearningEngine()
    strategy_engine = FakeStrategyEngine()
    weight_manager = FakeWeightManager()
    reinforcement_engine = FakeReinforcementEngine()

    return DecisionEngine(
        memory_manager=memory_manager,
        trust_manager=trust_manager,
        learning_engine=learning_engine,
        strategy_engine=strategy_engine,
        weight_manager=weight_manager,
        reinforcement_engine=reinforcement_engine,
    )


def test_decision_engine_returns_standard_contract(monkeypatch):
    """make_decision() should return the Phase-2 decision contract."""

    engine = build_decision_engine()

    # Prevent random exploration so this test checks normal selection.
    monkeypatch.setattr(
        "random.random",
        lambda: 1.0,
    )

    result = engine.make_decision(
        task_type="Analyze stock",
        critic_score=8,
        goal="default",
        available_workers=[
            "technical_worker",
            "sentiment_worker",
            "strategy_worker",
        ],
        trust_manager=engine.trust_manager,
    )

    assert isinstance(result, dict)

    assert "worker" in result
    assert "decision" in result
    assert "confidence" in result
    assert "risk" in result
    assert "factors" in result
    assert "reason" in result


def test_decision_engine_selects_registered_candidate():
    """Worker selection should come from the supplied worker candidates."""

    engine = build_decision_engine()

    worker = engine.select_worker(
        "Analyze stock",
        [
            "technical_worker",
            "sentiment_worker",
            "strategy_worker",
        ],
        engine.trust_manager,
    )

    assert worker in {
        "technical_worker",
        "sentiment_worker",
        "strategy_worker",
    }


def test_decision_engine_confidence_is_bounded(monkeypatch):
    """Decision confidence should remain within the [0, 1] range."""

    engine = build_decision_engine()

    monkeypatch.setattr(
        "random.random",
        lambda: 1.0,
    )

    result = engine.make_decision(
        task_type="Analyze stock",
        critic_score=8,
        goal="default",
        available_workers=[
            "technical_worker",
            "sentiment_worker",
            "strategy_worker",
        ],
        trust_manager=engine.trust_manager,
    )

    assert 0.0 <= result["confidence"] <= 1.0


def test_decision_engine_does_not_execute_workers(monkeypatch):
    """
    DecisionEngine should only make a decision.

    Worker execution belongs to ExecutionEngine.
    """

    engine = build_decision_engine()

    executed = []

    class WorkerProbe:
        """Worker-like object used to detect accidental execution."""

        def __init__(self, name):
            self.name = name

        def execute(self, task):
            """Record execution if the decision engine calls it."""
            executed.append((self.name, task))
            return {"success": True}

    workers = [
        WorkerProbe("technical_worker"),
        WorkerProbe("sentiment_worker"),
        WorkerProbe("strategy_worker"),
    ]

    monkeypatch.setattr(
        "random.random",
        lambda: 1.0,
    )

    result = engine.make_decision(
        task_type="Analyze stock",
        critic_score=8,
        goal="default",
        available_workers=[worker.name for worker in workers],
        trust_manager=engine.trust_manager,
    )

    assert result["worker"] in {
        "technical_worker",
        "sentiment_worker",
        "strategy_worker",
    }

    assert executed == []


def test_decision_engine_does_not_update_learning_during_decision(monkeypatch):
    """
    DecisionEngine should not create execution outcomes or update learning.

    Actual reward calculation and weight updates require an observed
    execution result and therefore belong after ExecutionEngine runs.
    """

    engine = build_decision_engine()

    reward_calls = []
    feedback_calls = []
    weight_update_calls = []

    # Spy on reinforcement calculations.
    def spy_calculate_reward(predicted, actual):
        reward_calls.append((predicted, actual))
        return 0.5

    def spy_generate_feedback(factors, reward):
        feedback_calls.append((factors, reward))
        return {}

    # Spy on adaptive weight updates.
    def spy_update_weights(feedback):
        weight_update_calls.append(feedback)

    monkeypatch.setattr(
        engine.reinforcement_engine,
        "calculate_reward",
        spy_calculate_reward,
    )

    monkeypatch.setattr(
        engine.reinforcement_engine,
        "generate_feedback",
        spy_generate_feedback,
    )

    monkeypatch.setattr(
        engine.weight_manager,
        "update_weights",
        spy_update_weights,
    )

    # Prevent exploration so the normal decision path is tested.
    monkeypatch.setattr(
        "random.random",
        lambda: 1.0,
    )

    result = engine.make_decision(
        task_type="Analyze stock",
        critic_score=8,
        goal="default",
        available_workers=[
            "technical_worker",
            "sentiment_worker",
            "strategy_worker",
        ],
        trust_manager=engine.trust_manager,
    )

    assert result["decision"] in {
        "EXECUTE",
        "ASK_USER",
        "BLOCK",
    }

    # Decision-making must not manufacture an actual outcome.
    assert reward_calls == []

    # Therefore no learning feedback should be generated.
    assert feedback_calls == []

    # Therefore adaptive weights must not change here.
    assert weight_update_calls == []


def test_decision_engine_learning_requires_execution_result(monkeypatch):
    """
    DecisionEngine must not perform reinforcement learning.

    The learning cycle requires an observed execution result and therefore
    belongs to the orchestration layer after ExecutionEngine completes.
    """

    engine = build_decision_engine()

    reward_calls = []
    feedback_calls = []
    weight_update_calls = []

    monkeypatch.setattr(
        engine.reinforcement_engine,
        "calculate_reward",
        lambda predicted, actual: reward_calls.append(
            (predicted, actual)
        ),
    )

    monkeypatch.setattr(
        engine.reinforcement_engine,
        "generate_feedback",
        lambda factors, reward: feedback_calls.append(
            (factors, reward)
        ),
    )

    monkeypatch.setattr(
        engine.weight_manager,
        "update_weights",
        lambda feedback: weight_update_calls.append(feedback),
    )

    monkeypatch.setattr(
        "random.random",
        lambda: 1.0,
    )

    result = engine.make_decision(
        task_type="Analyze stock",
        critic_score=8,
        goal="default",
        available_workers=[
            "technical_worker",
            "sentiment_worker",
            "strategy_worker",
        ],
        trust_manager=engine.trust_manager,
    )

    assert result["decision"] in {
        "EXECUTE",
        "ASK_USER",
        "BLOCK",
    }

    # DecisionEngine must stop at the decision contract.
    assert reward_calls == []
    assert feedback_calls == []
    assert weight_update_calls == []
