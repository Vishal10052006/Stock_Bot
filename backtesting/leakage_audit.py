"""Phase 13 leakage-audit helpers for frozen trading datasets."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

_FORBIDDEN_NON_LABEL_PATTERNS = (
    "future", "forward", "outcome", "next_return", "target_timestamp", "exit_timestamp",
)

@dataclass(frozen=True, slots=True)
class LeakageAuditCheck:
    name: str
    passed: bool
    detail: str

@dataclass(frozen=True, slots=True)
class LeakageAuditReport:
    checks: tuple[LeakageAuditCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(check.name for check in self.checks if not check.passed)

def audit_training_dataset(
    data: pd.DataFrame,
    *,
    feature_columns: tuple[str, ...],
    label_column: str = "label",
    timestamp_column: str = "timestamp",
    symbol_column: str = "symbol",
    available_at_column: str | None = None,
) -> LeakageAuditReport:
    """Audit the frozen supervised dataset before OOS/model evaluation."""
    checks: list[LeakageAuditCheck] = []
    checks.append(LeakageAuditCheck("dataframe", isinstance(data, pd.DataFrame), "Input must be a pandas DataFrame."))
    if not isinstance(data, pd.DataFrame):
        return LeakageAuditReport(tuple(checks))

    required = {timestamp_column, symbol_column, label_column, *feature_columns}
    missing = sorted(required.difference(data.columns))
    checks.append(LeakageAuditCheck("required_schema", not missing, f"Missing required columns: {missing}"))
    if missing:
        return LeakageAuditReport(tuple(checks))

    timestamps = pd.to_datetime(data[timestamp_column], utc=True, errors="coerce")
    checks.append(LeakageAuditCheck("timestamps_valid", not timestamps.isna().any(), "All decision timestamps must be valid and timezone-normalizable."))

    duplicate = data.duplicated(subset=[symbol_column, timestamp_column]).any()
    checks.append(LeakageAuditCheck("unique_decision_rows", not bool(duplicate), "Each symbol/decision-timestamp pair must be unique."))

    if not timestamps.isna().any():
        ordered = data.assign(__ts=timestamps).sort_values([symbol_column, "__ts"], kind="stable")
        monotonic = all(group["__ts"].is_monotonic_increasing for _, group in ordered.groupby(symbol_column, sort=False))
    else:
        monotonic = False
    checks.append(LeakageAuditCheck("per_symbol_chronology", monotonic, "Decision rows must be chronological within each symbol."))

    bad_feature_names = [column for column in feature_columns if any(token in column.lower() for token in _FORBIDDEN_NON_LABEL_PATTERNS)]
    checks.append(LeakageAuditCheck("feature_name_screen", not bad_feature_names, f"Future-looking feature names: {bad_feature_names}"))

    suspicious_dataset_columns = [
        column for column in data.columns
        if column != label_column
        and column not in {timestamp_column, symbol_column, available_at_column}
        and any(token in column.lower() for token in _FORBIDDEN_NON_LABEL_PATTERNS)
    ]
    checks.append(LeakageAuditCheck("dataset_future_field_screen", not suspicious_dataset_columns, f"Forbidden future-looking dataset fields: {suspicious_dataset_columns}"))

    numeric = True
    non_finite: list[str] = []
    for column in feature_columns:
        if not pd.api.types.is_numeric_dtype(data[column]):
            numeric = False
            continue
        series = pd.to_numeric(data[column], errors="coerce")
        if not series.notna().all() or series.isin([float("inf"), float("-inf")]).any():
            non_finite.append(column)
    checks.append(LeakageAuditCheck("numeric_finite_features", numeric and not non_finite, f"Non-numeric or non-finite features: {non_finite}"))

    checks.append(LeakageAuditCheck("label_excluded_from_features", label_column not in feature_columns, "The research label must never be a model feature."))

    if available_at_column is not None:
        present = available_at_column in data.columns
        checks.append(LeakageAuditCheck("availability_timestamp_present", present, f"Availability column {available_at_column!r} must exist."))
        if present and not timestamps.isna().any():
            available = pd.to_datetime(data[available_at_column], utc=True, errors="coerce")
            valid = not available.isna().any() and bool((available <= timestamps).all())
            checks.append(LeakageAuditCheck("availability_before_decision", valid, "Every feature availability timestamp must be <= decision time."))

    return LeakageAuditReport(tuple(checks))

def audit_future_perturbation_invariance(
    baseline: pd.DataFrame,
    perturbed: pd.DataFrame,
    *,
    cutoff_timestamp: str | pd.Timestamp,
    compare_columns: Iterable[str],
    timestamp_column: str = "timestamp",
    symbol_column: str = "symbol",
) -> LeakageAuditCheck:
    """Verify that changing future input cannot alter earlier observations."""
    cutoff = pd.Timestamp(cutoff_timestamp)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")

    left = baseline.copy()
    right = perturbed.copy()
    left[timestamp_column] = pd.to_datetime(left[timestamp_column], utc=True)
    right[timestamp_column] = pd.to_datetime(right[timestamp_column], utc=True)
    key = [symbol_column, timestamp_column]
    compare = list(compare_columns)
    left = left[left[timestamp_column] <= cutoff].set_index(key).sort_index()
    right = right[right[timestamp_column] <= cutoff].set_index(key).sort_index()
    if not left.index.equals(right.index):
        return LeakageAuditCheck("future_perturbation_invariance", False, "Baseline and perturbed datasets do not contain the same pre-cutoff decision rows.")
    equal = left[compare].equals(right[compare])
    detail = "Pre-cutoff outputs are unchanged after future-only input perturbation." if equal else "Future-only input perturbation changed pre-cutoff outputs."
    return LeakageAuditCheck("future_perturbation_invariance", equal, detail)