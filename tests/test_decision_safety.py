from pathlib import Path


def test_decision_engine_source_has_no_demo_randomness():
    source = Path("core/decision_engine.py").read_text()

    assert "import random" not in source
    assert "from random" not in source
    assert "random." not in source


def test_decision_result_uses_worker_key():
    source = Path("core/decision_engine.py").read_text()

    assert '"worker": worker_name' in source


def test_decision_result_does_not_use_worker_name_key():
    source = Path("core/decision_engine.py").read_text()

    assert '"worker_name": worker_name' not in source


def test_decision_engine_does_not_claim_market_confidence_from_critic_score():
    source = Path("core/decision_engine.py").read_text()

    assert "confidence = critic_score / 10" not in source
    assert "critic_score / 10" not in source


def test_legacy_decision_engine_fails_closed():
    source = Path("core/decision_engine.py").read_text()

    assert '"decision": "BLOCK"' in source
    assert '"confidence": None' in source
    assert '"risk": "high"' in source


def test_ceo_uses_decision_worker_key():
    source = Path("core/ceo.py").read_text()

    assert 'decision.get("worker")' in source
    assert 'decision.get("worker_name"' not in source


def test_ceo_does_not_use_fixed_critic_score_for_trading():
    source = Path("core/ceo.py").read_text()

    assert "critic_score=8" not in source


def test_ceo_does_not_train_from_generic_worker_result():
    source = Path("core/ceo.py").read_text()

    assert "self.reinforcement_engine.calculate_reward" not in source
    assert "self.weight_manager.update_weights(feedback)" not in source
