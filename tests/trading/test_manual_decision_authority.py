from __future__ import annotations

import ast
import importlib

import pandas as pd
import pytest

from trading.live.risk_context import LiveManualRiskContext


def test_v1_manual_decision_authority_lives_outside_paper_namespace() -> None:
    live = importlib.import_module("trading.live.manual_decision")
    legacy = importlib.import_module("trading.paper.canonical_paper_callback")

    assert legacy.CanonicalLiveDecision is live.CanonicalLiveDecision
    assert legacy.build_live_money_decision is live.build_live_money_decision


def test_manual_decision_module_has_no_broker_import_or_order_surface() -> None:
    source = importlib.import_module("trading.live.manual_decision").__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

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


def test_manual_decision_contains_no_synthetic_account_defaults() -> None:
    source = importlib.import_module("trading.live.manual_decision").__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        source_text = handle.read()

    for synthetic in (
        "realized_pnl=0.0",
        "unrealized_pnl=0.0",
        "open_positions=0",
        "trades_today=0",
        "gross_exposure=0.0",
        "symbol_already_open=False",
        "liquidity_available=True",
        "kill_switch_active=False",
    ):
        assert synthetic not in source_text


def test_live_manual_risk_context_requires_fresh_observed_state() -> None:
    decision_time = pd.Timestamp("2026-10-03T10:00:00+05:30")
    context = LiveManualRiskContext(
        as_of=decision_time - pd.Timedelta(seconds=10),
        source="manual_account_snapshot",
        available_equity=100_000.0,
        day_start_equity=100_000.0,
    )

    assert context.validation_error(decision_time) is None


def test_live_manual_risk_context_blocks_stale_state() -> None:
    decision_time = pd.Timestamp("2026-10-03T10:00:00+05:30")
    context = LiveManualRiskContext(
        as_of=decision_time - pd.Timedelta(seconds=31),
        source="manual_account_snapshot",
        available_equity=100_000.0,
        day_start_equity=100_000.0,
    )

    assert context.validation_error(decision_time) is not None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"available_equity": 0.0},
        {"day_start_equity": 0.0},
        {"max_age_seconds": 0.0},
    ],
)
def test_live_manual_risk_context_rejects_invalid_state(kwargs) -> None:
    with pytest.raises(ValueError):
        LiveManualRiskContext(
            as_of=pd.Timestamp("2026-10-03T10:00:00+05:30"),
            source="manual_account_snapshot",
            available_equity=kwargs.get("available_equity", 100_000.0),
            day_start_equity=kwargs.get("day_start_equity", 100_000.0),
            max_age_seconds=kwargs.get("max_age_seconds", 30.0),
        )
