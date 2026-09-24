"""Portfolio manager policy tests."""

from __future__ import annotations

import pandas as pd

from portfolio.contracts import (
    PortfolioAction,
    PortfolioLimits,
    PortfolioPosition,
    PortfolioSnapshot,
    TradeIntent,
)
from portfolio.manager import PortfolioManager


def state() -> PortfolioSnapshot:
    return PortfolioSnapshot(
        pd.Timestamp("2026-01-01", tz="Asia/Kolkata"),
        100000.0,
        (PortfolioPosition("INFY", 10, 1500, "IT"),),
    )


def test_unconfigured_policies_do_not_invent_rejections() -> None:
    manager = PortfolioManager(PortfolioLimits())
    decision = manager.evaluate(state(), TradeIntent("TCS", 10, 3500, "BUY", "IT", "d1"))
    assert decision.action is PortfolioAction.APPROVE


def test_max_positions_rejects_new_symbol() -> None:
    manager = PortfolioManager(PortfolioLimits(max_positions=1))
    decision = manager.evaluate(state(), TradeIntent("TCS", 1, 3500, "BUY", "IT", "d2"))
    assert decision.action is PortfolioAction.REJECT
    assert decision.reason_code == "MAX_POSITIONS"


def test_existing_symbol_does_not_increase_position_count() -> None:
    manager = PortfolioManager(PortfolioLimits(max_positions=1))
    decision = manager.evaluate(state(), TradeIntent("INFY", 1, 1500, "BUY", "IT", "d3"))
    assert decision.action is PortfolioAction.APPROVE


def test_gross_exposure_rejects_projected_breach() -> None:
    manager = PortfolioManager(PortfolioLimits(max_gross_exposure_fraction=0.20))
    decision = manager.evaluate(state(), TradeIntent("TCS", 3, 3500, "BUY", "IT", "d4"))
    assert decision.action is PortfolioAction.REJECT
    assert decision.reason_code == "MAX_GROSS_EXPOSURE"


def test_symbol_exposure_rejects_projected_breach() -> None:
    manager = PortfolioManager(PortfolioLimits(max_symbol_exposure_fraction=0.20))
    decision = manager.evaluate(state(), TradeIntent("INFY", 5, 1500, "BUY", "IT", "d5"))
    assert decision.action is PortfolioAction.REJECT
    assert decision.reason_code == "MAX_SYMBOL_EXPOSURE"


def test_sector_exposure_rejects_projected_breach() -> None:
    manager = PortfolioManager(PortfolioLimits(max_sector_exposure_fraction=0.20))
    decision = manager.evaluate(state(), TradeIntent("TCS", 2, 3500, "BUY", "IT", "d6"))
    assert decision.action is PortfolioAction.REJECT
    assert decision.reason_code == "MAX_SECTOR_EXPOSURE"


def test_decision_fingerprint_is_deterministic() -> None:
    manager = PortfolioManager(PortfolioLimits(max_gross_exposure_fraction=0.5))
    intent = TradeIntent("TCS", 1, 3500, "BUY", "IT", "d7")
    first = manager.evaluate(state(), intent)
    second = manager.evaluate(state(), intent)
    assert first.fingerprint == second.fingerprint


def test_existing_symbol_uses_existing_sector_when_intent_omits_sector() -> None:
    manager = PortfolioManager(PortfolioLimits(max_sector_exposure_fraction=0.20))
    decision = manager.evaluate(state(), TradeIntent("INFY", 1, 1500, "BUY", None, "d8"))
    assert decision.action is PortfolioAction.REJECT
    assert decision.reason_code == "MAX_SECTOR_EXPOSURE"
