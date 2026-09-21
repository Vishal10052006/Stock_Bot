import pandas as pd

from backtesting.audit import audit_dataset


def test_clean_dataset_passes_structural_audit() -> None:
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01 09:15:00+05:30",
                    "2026-01-01 09:20:00+05:30",
                ],
                utc=True,
            ),
            "symbol": ["ITC", "ITC"],
            "feature_a": [1.0, 2.0],
        }
    )

    report = audit_dataset(
        data,
        feature_columns=("feature_a",),
    )

    assert report.passed


def test_future_named_feature_is_rejected() -> None:
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01 09:15:00+05:30",
                ],
                utc=True,
            ),
            "symbol": ["ITC"],
            "future_return": [1.0],
        }
    )

    report = audit_dataset(
        data,
        feature_columns=("future_return",),
    )

    assert not report.passed
