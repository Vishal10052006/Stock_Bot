from pathlib import Path


def test_decision_engine_has_no_random_dependency():
    source = Path("core/decision_engine.py").read_text()

    assert "import random" not in source
    assert "from random" not in source
    assert "random." not in source


def test_decision_engine_has_no_synthetic_random_outcome():
    source = Path("core/decision_engine.py").read_text()

    assert "random.uniform" not in source
    assert "actual = random" not in source


def test_execution_path_does_not_use_reinforcement_without_market_outcome():
    source = Path("execution/execution_engine.py").read_text()

    # Worker success is not a trading outcome.
    assert "self.reinforcement_engine.update(command, result)" not in source


def test_ceo_does_not_train_from_generic_worker_result():
    source = Path("core/ceo.py").read_text()

    assert "self.reinforcement_engine.calculate_reward" not in source
    assert "self.weight_manager.update_weights(feedback)" not in source


def test_reinforcement_engine_does_not_invent_market_outcomes():
    source = Path("learning/reinforcement_engine.py").read_text()

    assert "random" not in source.lower()
