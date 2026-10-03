from __future__ import annotations

import importlib


def test_v1_manual_decision_authority_lives_outside_paper_namespace() -> None:
    live = importlib.import_module("trading.live.manual_decision")
    legacy = importlib.import_module("trading.paper.canonical_paper_callback")

    assert legacy.CanonicalLiveDecision is live.CanonicalLiveDecision
    assert legacy.build_live_money_decision is live.build_live_money_decision


def test_manual_decision_module_has_no_broker_execution_surface() -> None:
    source = importlib.import_module("trading.live.manual_decision").__file__
    assert source is not None
    text = open(source, encoding="utf-8").read()
    assert "broker" not in text.lower() or "broker execution" in text.lower()
    assert "submit_order" not in text
    assert "place_order" not in text

