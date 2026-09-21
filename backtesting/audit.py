"""AB-42 causal, leakage and evaluation-integrity audit."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class AuditCheck:
    """One auditable integrity check."""

    name: str
    passed: bool
    severity: str
    detail: str


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Immutable aggregate audit result."""

    checks: tuple[AuditCheck, ...]

    @property
    def passed(self) -> bool:
        """Return True only when every audit check passes."""
        return all(check.passed for check in self.checks)


_FUTURE_NAME_PATTERNS = (
    "future",
    "forward",
    "target",
    "label",
    "outcome",
    "exit",
    "next_return",
)


def audit_dataset(
    data: pd.DataFrame,
    *,
    feature_columns: tuple[str, ...],
    timestamp_column: str = "timestamp",
    available_at_column: str | None = None,
) -> AuditReport:
    """Run structural leakage and temporal-integrity checks.

    This audit is an automated screening layer. Passing it does not prove
    the complete research process is free from every possible bias.
    """

    checks: list[AuditCheck] = []

    # ---------------------------------------------------------------
    # 1. DataFrame contract
    # ---------------------------------------------------------------
    dataframe_ok = isinstance(data, pd.DataFrame)

    checks.append(
        AuditCheck(
            name="dataframe",
            passed=dataframe_ok,
            severity="ERROR",
            detail="Input must be a pandas DataFrame.",
        )
    )

    if not dataframe_ok:
        return AuditReport(tuple(checks))

    # ---------------------------------------------------------------
    # 2. Timestamp contract
    # ---------------------------------------------------------------
    timestamp_ok = timestamp_column in data.columns

    checks.append(
        AuditCheck(
            name="timestamp_present",
            passed=timestamp_ok,
            severity="ERROR",
            detail="Decision timestamp must exist.",
        )
    )

    timestamps: pd.Series | None = None

    if timestamp_ok:
        timestamps = pd.to_datetime(
            data[timestamp_column],
            utc=True,
            errors="coerce",
        )

        valid_timestamps = not timestamps.isna().any()

        checks.append(
            AuditCheck(
                name="timestamp_valid",
                passed=valid_timestamps,
                severity="ERROR",
                detail="All decision timestamps must be valid.",
            )
        )

        if valid_timestamps:
            checks.append(
                AuditCheck(
                    name="chronological",
                    passed=timestamps.is_monotonic_increasing,
                    severity="ERROR",
                    detail="Rows must be chronologically ordered.",
                )
            )

    # ---------------------------------------------------------------
    # 3. Feature schema
    # ---------------------------------------------------------------
    missing_features = [
        column
        for column in feature_columns
        if column not in data.columns
    ]

    checks.append(
        AuditCheck(
            name="feature_schema",
            passed=not missing_features,
            severity="ERROR",
            detail=f"Missing features: {missing_features}",
        )
    )

    # ---------------------------------------------------------------
    # 4. Suspicious future-looking feature names
    # ---------------------------------------------------------------
    suspicious_features = [
        column
        for column in feature_columns
        if any(
            token in column.lower()
            for token in _FUTURE_NAME_PATTERNS
        )
    ]

    checks.append(
        AuditCheck(
            name="future_field_screen",
            passed=not suspicious_features,
            severity="ERROR",
            detail=(
                "Suspicious feature names: "
                f"{suspicious_features}"
            ),
        )
    )

    # ---------------------------------------------------------------
    # 5. Duplicate decision rows
    # ---------------------------------------------------------------
    duplicate_columns = [
        column
        for column in (
            timestamp_column,
            "symbol",
        )
        if column in data.columns
    ]

    if duplicate_columns:
        duplicates = data.duplicated(
            subset=duplicate_columns
        ).any()
    else:
        duplicates = False

    checks.append(
        AuditCheck(
            name="duplicate_decision_rows",
            passed=not duplicates,
            severity="ERROR",
            detail=(
                "Duplicate symbol/timestamp decisions "
                "are not allowed."
            ),
        )
    )

    # ---------------------------------------------------------------
    # 6. Feature availability timestamp
    # ---------------------------------------------------------------
    if available_at_column is not None:
        available_ok = available_at_column in data.columns

        checks.append(
            AuditCheck(
                name="availability_timestamp_present",
                passed=available_ok,
                severity="ERROR",
                detail=(
                    "available_at column must exist "
                    "when supplied."
                ),
            )
        )

        if (
            available_ok
            and timestamp_ok
            and timestamps is not None
            and not timestamps.isna().any()
        ):
            available_at = pd.to_datetime(
                data[available_at_column],
                utc=True,
                errors="coerce",
            )

            availability_valid = (
                not available_at.isna().any()
                and bool(
                    (
                        available_at
                        <= timestamps
                    ).all()
                )
            )

            checks.append(
                AuditCheck(
                    name="feature_available_before_decision",
                    passed=availability_valid,
                    severity="ERROR",
                    detail=(
                        "Feature availability must not occur "
                        "after the decision timestamp."
                    ),
                )
            )

    return AuditReport(tuple(checks))
