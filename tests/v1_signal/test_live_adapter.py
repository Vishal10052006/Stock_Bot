"""Tests for live canonical-paper -> V1 signal adaptation."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from trading.strategy.models import StrategyDecision, StrategyDirection
from v1_signal import V1Signal, build_v1_signal_from_decision


TIMESTAMP = pd.Timestamp("2026-09-27T09:30:00Z")


def _decision(direction=StrategyDirection.LONG):
    probabilities = pd.DataFrame(
        [{
            "LONG_SUCCESS": 0.70,
            "SHORT_SUCCESS": 0.20,
            "NO_EDGE": 0.10,
        }]
    )
    prediction = SimpleNamespace(
        timestamp=TIMESTAMP,
        symbol="ITC",
        predicted_class="LONG_SUCCESS",
        probabilities=probabilities,
        model_version="phase9-logistic-v1",
        feature_version="v1.0",
        calibration_version="iso-v1",
    )
    strategy = StrategyDecision(
        timestamp=TIMESTAMP,
        symbol="ITC",
        direction=direction,
        strategy_version="STRAT-v1.0",
        rationale="Trend and prediction conditions passed.",
        prediction_class="LONG_SUCCESS",
        prediction_probability=0.70,
        prediction_margin=0.50,
        regime="TREND_UP",
        regime_probability=0.90,
        entry_reference=100.0,
        stop_reference=98.0,
        target_reference=104.0,
        provenance={"data_version": "upstox-live-v1"},
        features={"rvol_20": 1.5},
    )
    return SimpleNamespace(
        prediction=prediction,
        strategy=strategy,
        risk_status="APPROVED",
        risk_reason="Risk limits passed.",
        paper_order_status="FILLED",
        trade_id="TR-001",
    )


def test_live_paper_decision_becomes_canonical_buy():
    contract = build_v1_signal_from_decision(
        _decision(),
        valid_until=TIMESTAMP + pd.Timedelta(minutes=5),
    )

    assert contract.signal is V1Signal.BUY
    assert contract.entry == 100.0
    assert contract.stop_loss == 98.0
    assert contract.target == 104.0
    assert contract.risk_reward == 2.0
    assert contract.confidence == 0.70
    assert contract.prediction_evidence["probabilities"]["NO_EDGE"] == 0.10
    assert contract.authority == "HUMAN_REVIEW_ONLY"
    assert contract.broker_execution is False
    assert contract.fingerprint if hasattr(contract, "fingerprint") else contract.as_dict()["fingerprint"]


def test_live_paper_no_trade_becomes_wait_without_fabricated_probabilities():
    decision = _decision(StrategyDirection.NO_TRADE)
    decision.strategy = StrategyDecision(
        timestamp=TIMESTAMP,
        symbol="ITC",
        direction=StrategyDirection.NO_TRADE,
        strategy_version="STRAT-v1.0",
        rationale="Prediction edge did not meet strategy policy.",
        prediction_class="NO_EDGE",
        prediction_probability=0.10,
        prediction_margin=0.02,
        regime="SIDEWAYS",
        regime_probability=0.80,
    )

    contract = build_v1_signal_from_decision(
        decision,
        valid_until=TIMESTAMP + pd.Timedelta(minutes=5),
    )

    assert contract.signal is V1Signal.WAIT
    assert contract.entry is None
    assert contract.risk_reward is None
    assert contract.prediction_evidence["probabilities"] == {
        "LONG_SUCCESS": 0.70,
        "SHORT_SUCCESS": 0.20,
        "NO_EDGE": 0.10,
    }


def test_future_research_context_is_rejected():
    context = SimpleNamespace(
        as_of=TIMESTAMP + pd.Timedelta(minutes=1),
        research_stance="POSITIVE",
        research_score=0.8,
        research_confidence=0.9,
        evidence_count=2,
        source_count=2,
        conflict_score=0.0,
        research_version="research-v1",
    )

    with pytest.raises(ValueError, match="future V1 evidence"):
        build_v1_signal_from_decision(
            _decision(),
            valid_until=TIMESTAMP + pd.Timedelta(minutes=5),
            research_context=context,
        )
