"""End-to-end Analysis integration audit tests."""
from __future__ import annotations

import pandas as pd

from intelligence.analysis.audit import audit_analysis_chain
from intelligence.analysis.engine import AnalysisEngine
from intelligence.analysis.contracts import AnalysisInput
from ml.integration.analysis_prediction import PredictionContext
from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.strategy.models import StrategyDecision, StrategyDirection


def _analysis_context():
    return AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
            symbol="RELIANCE",
            features={"rsi_14": 60.0},
            research_context={
                "symbol": "RELIANCE",
                "as_of": "2026-09-20T10:20:00+05:30",
            },
            fundamental_context={
                "available": True,
                "available_at": "2026-09-20T09:30:00+05:30",
            },
            valuation_context={
                "available": True,
                "as_of": "2026-09-20T10:15:00+05:30",
            },
            data_version="market-v1",
            feature_version="features-v1",
        )
    )


def _downstream(context):
    prediction = PredictionContext(
        timestamp=context.timestamp,
        symbol=context.symbol,
        probabilities=pd.DataFrame(
            [[0.70, 0.20, 0.10]],
            columns=["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"],
        ),
        predicted_class="LONG_SUCCESS",
        model_version="phase9-test-v1",
        feature_version=context.feature_version,
        analysis_version=context.analysis_version,
    )
    strategy = StrategyDecision(
        timestamp=context.timestamp,
        symbol=context.symbol,
        direction=StrategyDirection.LONG,
        strategy_version="v1.0",
        rationale="test-only deterministic strategy decision",
    )
    risk = RiskDecision(
        timestamp=context.timestamp,
        symbol=context.symbol,
        status=RiskDecisionStatus.APPROVED,
        strategy_direction=strategy.direction,
        reason="test-only deterministic risk decision",
    )
    return prediction, strategy, risk


def test_full_analysis_downstream_boundary_audit_passes() -> None:
    context = _analysis_context()
    prediction, strategy, risk = _downstream(context)

    report = audit_analysis_chain(
        context,
        prediction=prediction,
        strategy=strategy,
        risk=risk,
    )

    assert report.passed is True
    assert all(check.passed for check in report.checks)


def test_analysis_chain_audit_rejects_future_context() -> None:
    context = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
            symbol="RELIANCE",
            features={"rsi_14": 60.0},
            research_context={
                "symbol": "RELIANCE",
                "as_of": "2026-09-20T10:30:00+05:30",
            },
            fundamental_context={
                "available": True,
                "available_at": "2026-09-20T10:30:00+05:30",
            },
            valuation_context={
                "available": True,
                "as_of": "2026-09-20T10:30:00+05:30",
            },
        )
    )

    report = audit_analysis_chain(context)

    assert report.passed is False
    failed = {check.name for check in report.checks if not check.passed}
    assert {
        "research_not_future",
        "fundamental_not_future",
        "valuation_not_future",
    } <= failed


def test_analysis_context_owns_mapping_inputs() -> None:
    features = {"rsi_14": 60.0}
    context = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
            symbol="RELIANCE",
            features=features,
        )
    )

    features["rsi_14"] = 1.0

    assert context.feature_vector["rsi_14"] == 60.0
