from __future__ import annotations

import ast
import importlib


def test_v1_manual_decision_authority_lives_outside_paper_namespace() -> None:
    live = importlib.import_module("trading.live.manual_decision")
    legacy = importlib.import_module("trading.paper.canonical_paper_callback")

    assert legacy.CanonicalLiveDecision is live.CanonicalLiveDecision
    assert legacy.build_live_money_decision is live.build_live_money_decision


def test_manual_decision_module_has_no_broker_import_or_order_surface() -> None:
    source = importlib.import_module("trading.live.manual_decision").__file__
    assert source is not None
    tree = ast.parse(open(source, encoding="utf-8").read())

    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    assert all("broker" not in name.lower() for name in imported)
    source_text = ast.unparse(tree)
    assert "submit_order" not in source_text
    assert "place_order" not in source_text
