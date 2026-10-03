from __future__ import annotations

from pathlib import Path

def test_v1_runtime_source_enables_live_account_gate_for_operator_snapshots():
    source = Path(__file__).resolve().parents[2] / "trading" / "live" / "manual_review_runtime.py"
    text = source.read_text(encoding="utf-8")
    assert "require_live_account_context=True" in text
