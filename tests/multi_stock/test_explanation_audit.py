from __future__ import annotations

import pandas as pd
import pytest

from multi_stock.decision_explanation import build_decision_explanation
from multi_stock.explanation_audit import audit_decision_explanation


def test_valid_no_trade_explanation_audits_cleanly():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    explanation = build_decision_explanation(
        ts,
        "RELIANCE.NS",
        strategy={
            "timestamp": ts,
            "symbol": "RELIANCE.NS",
            "direction": "NO_TRADE",
            "reason": "Strategy condition failed.",
        },
    )
    result = audit_decision_explanation(explanation, expected_symbol="RELIANCE.NS")
    assert result.valid
    assert result.usable
    assert result.reasons == ()


def test_inconsistent_outcome_is_rejected():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    explanation = build_decision_explanation(
        ts,
        "RELIANCE.NS",
        strategy={
            "timestamp": ts,
            "symbol": "RELIANCE.NS",
            "direction": "NO_TRADE",
            "reason": "Strategy condition failed.",
        },
    )
    object.__setattr__(explanation, "outcome", "LONG")
    result = audit_decision_explanation(explanation)
    assert not result.valid
    assert "EXPLANATION_OUTCOME_STRATEGY_MISMATCH" in result.reasons


def test_expected_symbol_mismatch_is_rejected():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    explanation = build_decision_explanation(ts, "RELIANCE.NS")
    result = audit_decision_explanation(explanation, expected_symbol="TCS.NS")
    assert not result.valid
    assert "EXPLANATION_SYMBOL_MISMATCH" in result.reasons


def test_unknown_stage_is_rejected():
    ts = pd.Timestamp("2026-10-02 10:00:00", tz="Asia/Kolkata")
    explanation = build_decision_explanation(ts, "RELIANCE.NS")
    from multi_stock.decision_explanation import DecisionExplanationItem
    item = DecisionExplanationItem("Unknown", ts, "OBSERVED", "evidence", "test")
    object.__setattr__(explanation, "items", (item,))
    result = audit_decision_explanation(explanation)
    assert not result.valid
    assert "EXPLANATION_UNKNOWN_STAGE:Unknown" in result.reasons
