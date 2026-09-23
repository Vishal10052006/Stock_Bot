import numpy as np
import pandas as pd
import pytest

from ml.models.boosting import BoostingConfig, OptionalBoostingOutcomeModel


def test_boosting_config_rejects_unknown_backend() -> None:
    with pytest.raises(ValueError, match="backend"):
        BoostingConfig(backend="unknown")


def test_optional_boosting_validates_training_classes() -> None:
    model = OptionalBoostingOutcomeModel(BoostingConfig(backend="xgboost"))
    X = np.ones((3, 2))
    y = pd.Series(["LONG_SUCCESS", "SHORT_SUCCESS", "LONG_SUCCESS"])
    with pytest.raises(ValueError, match="missing classes"):
        model.fit(X, y)
