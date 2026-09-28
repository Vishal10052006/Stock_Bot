import pandas as pd

from ml.prediction.uncertainty import (
    predictive_entropy,
    probability_margin,
    variation_ratio,
)


def test_probability_uncertainty_measures() -> None:
    probabilities = pd.DataFrame(
        [
            {"LONG_SUCCESS": 0.8, "SHORT_SUCCESS": 0.1, "NO_EDGE": 0.1},
            {"LONG_SUCCESS": 1 / 3, "SHORT_SUCCESS": 1 / 3, "NO_EDGE": 1 / 3},
        ]
    )
    entropy = predictive_entropy(probabilities)
    margin = probability_margin(probabilities)
    variation = variation_ratio(probabilities)

    assert entropy.iloc[0] < entropy.iloc[1]
    assert margin.iloc[0] > margin.iloc[1]
    assert variation.iloc[0] < variation.iloc[1]
