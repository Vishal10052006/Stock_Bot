"""Static safety checks for the Self-Learning Engine."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_self_learning_source_has_no_broker_dependency() -> None:
    """The learning package must remain outside broker execution authority."""
    for path in (ROOT / "self_learning").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "broker" not in source.lower()
        assert "order" not in source.lower() or path.name in {"contracts.py", "promotion.py", "orchestrator.py"}


def test_self_learning_does_not_modify_hard_risk_controls() -> None:
    """Learning code must not expose hard-risk mutation surfaces."""
    for path in (ROOT / "self_learning").glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert "risk_per_trade" not in source
        assert "daily_loss_limit" not in source
        assert "kill_switch" not in source


def test_self_learning_does_not_enable_live_execution() -> None:
    """No learning module may expose a live execution enable switch."""
    for path in (ROOT / "self_learning").glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert "live_execution_enabled" not in source
        assert "enable_live" not in source
