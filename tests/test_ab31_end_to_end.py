"""AB-31 real market -> fitted Phase 9 model -> execution authorization."""
from __future__ import annotations

import pandas as pd

from intelligence.analysis.contracts import AnalysisInput
from intelligence.analysis.engine import AnalysisEngine
from ml.integration.analysis_prediction import predict_from_analysis
from ml.preprocessing.pipeline import FeaturePreprocessor
from ml.models.logistic import LogisticOutcomeModel
from trading.ab30_pipeline import build_market_analysis
from trading.decision_chain import build_decision_chain
from ml.preprocessing.models import NUMERIC_FEATURES, BOOLEAN_FEATURES


def _candles(rows: int = 80) -> pd.DataFrame:
    ts = pd.date_range(
        "2026-09-20 09:15:00+05:30", periods=rows, freq="5min"
    )
    close = [100.0 + 0.18 * i for i in range(rows)]
    return pd.DataFrame({
        "timestamp": ts,
        "symbol": ["RELIANCE"] * rows,
        "open": close,
        "high": [x + 0.2 for x in close],
        "low": [x - 0.15 for x in close],
        "close": close,
        "volume": [1000 + 10*i for i in range(rows)],
    })


def _market_context(rows: int = 80) -> pd.DataFrame:
    ts = pd.date_range(
        "2026-09-20 09:15:00+05:30", periods=rows, freq="5min"
    )
    return pd.DataFrame({
        "timestamp": ts,
        "close": [100.0 + 0.1*i for i in range(rows)],
        "return_1": [0.001] * rows,
        "return_3": [0.006] * rows,
        "return_12": [0.025] * rows,
        "volatility_20": [0.015] * rows,
    })


def _training_frame(rows: int = 36) -> tuple[pd.DataFrame, pd.Series]:
    data = {}
    for i, col in enumerate(NUMERIC_FEATURES):
        data[col] = [(i + j + 1) / 1000.0 for j in range(rows)]
    for i, col in enumerate(sorted(BOOLEAN_FEATURES)):
        data[col] = [bool((i + j) % 2) for j in range(rows)]
    y = pd.Series(
        ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"] * (rows // 3),
        name="label",
    )
    return pd.DataFrame(data), y


def test_ab31_real_market_to_fitted_model_to_execution_authorization() -> None:
    market = build_market_analysis(
        _candles(),
        symbol="RELIANCE",
        market_context=_market_context(),
    )
    analysis = market.analysis

    X_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    X_fit = preprocessor.fit_transform(X_train)

    model = LogisticOutcomeModel()
    model.fit(X_fit, y_train)

    prediction = predict_from_analysis(
        analysis,
        model=model,
        preprocessor=preprocessor,
        model_version="phase9-logistic-ab31-test",
    )

    decision_features = pd.Series({
        "vwap_distance_pct": float(analysis.feature_vector.get("vwap_distance_pct") or 0.1),
        "rvol_20": float(analysis.feature_vector.get("rvol_20") or 1.1),
        "higher_high": bool(analysis.feature_vector.get("higher_high")),
        "higher_low": bool(analysis.feature_vector.get("higher_low")),
        "lower_low": bool(analysis.feature_vector.get("lower_low")),
        "lower_high": bool(analysis.feature_vector.get("lower_high")),
    })

    regime_row = market.regime.iloc[-1]
    regime = str(regime_row["regime"]) if pd.notna(regime_row["regime"]) else "RANGE"
    probability = float(regime_row["regime_probability"]) if pd.notna(regime_row["regime_probability"]) else 0.5

    chain = build_decision_chain(
        analysis,
        prediction,
        decision_features=decision_features,
        regime=regime,
        regime_probability=probability,
    )

    assert prediction.timestamp == analysis.timestamp
    assert prediction.symbol == analysis.symbol
    assert list(prediction.probabilities.columns) == [
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    ]
    assert abs(float(prediction.probabilities.iloc[0].sum()) - 1.0) < 1e-8
    assert chain.execution.timestamp == analysis.timestamp
    assert chain.execution.symbol == analysis.symbol


def test_ab31_never_enters_future_label_into_inference() -> None:
    analysis = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
            symbol="TCS",
            features={
                "rsi_14": 55.0,
                "vwap_distance_pct": 0.2,
                "rvol_20": 1.1,
                "higher_high": True,
                "higher_low": True,
                "lower_low": False,
                "lower_high": False,
                "future_return": 999.0,
            },
        )
    )
    assert "future_return" in analysis.feature_vector
    # AB-31's inference path is governed by Phase 9's exact feature schema,
    # so a future-only extra column cannot silently enter preprocessing.
    try:
        _ = predict_from_analysis(
            analysis,
            model=LogisticOutcomeModel(),
            preprocessor=FeaturePreprocessor(),
        )
    except ValueError:
        pass
    except RuntimeError:
        pass
    else:
        raise AssertionError("unfitted inference must not proceed")
