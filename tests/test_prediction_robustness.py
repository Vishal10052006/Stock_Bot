import pandas as pd

from ml.evaluation.robustness import evaluate_robustness


def test_robustness_evaluation_slices_existing_predictions() -> None:
    y_true = pd.Series(["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"])
    probabilities = pd.DataFrame(
        [
            {"LONG_SUCCESS": 0.8, "SHORT_SUCCESS": 0.1, "NO_EDGE": 0.1},
            {"LONG_SUCCESS": 0.1, "SHORT_SUCCESS": 0.8, "NO_EDGE": 0.1},
            {"LONG_SUCCESS": 0.1, "SHORT_SUCCESS": 0.1, "NO_EDGE": 0.8},
        ]
    )
    metadata = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-09-20 10:00:00+05:30",
                    "2026-09-20 10:05:00+05:30",
                    "2026-09-21 10:00:00+05:30",
                ],
                utc=True,
            ),
            "symbol": ["AAA", "AAA", "BBB"],
            "regime": ["LOW_VOLATILITY", "HIGH_VOLATILITY", "LOW_VOLATILITY"],
        }
    )
    report = evaluate_robustness(y_true, probabilities, metadata)
    assert len(report.by_regime) == 2
    assert len(report.by_symbol) == 2
    assert len(report.by_date) == 2
