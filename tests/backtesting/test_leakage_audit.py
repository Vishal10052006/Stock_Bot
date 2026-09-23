import pandas as pd

from backtesting.leakage_audit import audit_future_perturbation_invariance, audit_training_dataset

def _dataset() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.to_datetime(["2026-01-01 09:15:00+05:30", "2026-01-01 09:20:00+05:30", "2026-01-01 09:25:00+05:30"], utc=True),
        "symbol": ["ITC", "ITC", "ITC"],
        "feature_a": [1.0, 2.0, 3.0],
        "feature_b": [4.0, 5.0, 6.0],
        "label": ["NO_EDGE", "LONG_SUCCESS", "SHORT_SUCCESS"],
    })

def test_clean_training_dataset_passes_phase13_audit() -> None:
    report = audit_training_dataset(_dataset(), feature_columns=("feature_a", "feature_b"))
    assert report.passed
    assert report.failed_checks == ()

def test_future_field_outside_label_is_rejected() -> None:
    data = _dataset().assign(outcome_timestamp=_dataset()["timestamp"])
    report = audit_training_dataset(data, feature_columns=("feature_a", "feature_b"))
    assert not report.passed
    assert "dataset_future_field_screen" in report.failed_checks

def test_label_cannot_be_a_feature() -> None:
    report = audit_training_dataset(_dataset(), feature_columns=("feature_a", "label"))
    assert not report.passed
    assert "label_excluded_from_features" in report.failed_checks

def test_future_perturbation_passes_when_only_future_row_changes() -> None:
    baseline = _dataset()
    perturbed = baseline.copy()
    perturbed.loc[2, "feature_a"] = 999.0
    check = audit_future_perturbation_invariance(baseline, perturbed, cutoff_timestamp="2026-01-01 09:20:00+05:30", compare_columns=("feature_a", "feature_b"))
    assert check.passed

def test_future_perturbation_detects_changed_prior_output() -> None:
    baseline = _dataset()
    perturbed = baseline.copy()
    perturbed.loc[1, "feature_a"] = 999.0
    check = audit_future_perturbation_invariance(baseline, perturbed, cutoff_timestamp="2026-01-01 09:20:00+05:30", compare_columns=("feature_a", "feature_b"))
    assert not check.passed