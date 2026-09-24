"""Static safety checks for the Self-Learning Engine."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_self_learning_has_no_broker_imports() -> None:
    """Learning code must not import broker or execution adapters."""
    for path in (ROOT / "self_learning").glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert "from broker" not in source
        assert "import broker" not in source
        assert "upstox" not in source


def test_self_learning_does_not_mutate_hard_risk_controls() -> None:
    """Learning code must not expose direct hard-risk mutation fields."""
    forbidden = ("risk_per_trade", "daily_loss_limit", "kill_switch", "max_daily_loss")
    for path in (ROOT / "self_learning").glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert all(token not in source for token in forbidden)


def test_self_learning_does_not_enable_live_execution() -> None:
    """Learning code must not contain live-execution enablement hooks."""
    forbidden = ("live_execution_enabled", "enable_live", "place_order", "cancel_order")
    for path in (ROOT / "self_learning").glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert all(token not in source for token in forbidden)
