"""Distribution drift calculations for monitoring.

PSI is descriptive telemetry. It does not modify models or make trades.

References:
    docs/MONITORING_ENGINE.md
    research/monitoring/drift.py
"""

from __future__ import annotations

import math
from typing import Sequence


def population_stability_index(
    reference: Sequence[float],
    current: Sequence[float],
    *,
    bins: int = 10,
    epsilon: float = 1e-6,
) -> float:
    """Calculate PSI with equal-width bins spanning both samples."""
    if not reference or not current:
        raise ValueError("reference and current samples must be non-empty")
    if bins < 2:
        raise ValueError("bins must be >= 2")
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")

    values = [float(value) for value in (*reference, *current)]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("drift samples must contain finite values")

    low = min(values)
    high = max(values)
    if low == high:
        return 0.0

    edges = [
        low + (high - low) * index / bins
        for index in range(bins + 1)
    ]

    def distribution(sample: Sequence[float]) -> list[float]:
        counts = [0] * bins
        for raw_value in sample:
            value = float(raw_value)
            index = bins - 1
            for candidate in range(bins):
                if edges[candidate] <= value < edges[candidate + 1]:
                    index = candidate
                    break
            counts[index] += 1

        total = len(sample)
        return [max(count / total, epsilon) for count in counts]

    reference_distribution = distribution(reference)
    current_distribution = distribution(current)

    return sum(
        (current_share - reference_share)
        * math.log(current_share / reference_share)
        for reference_share, current_share in zip(
            reference_distribution,
            current_distribution,
            strict=True,
        )
    )


def max_pairwise_psi(
    reference_columns: dict[str, Sequence[float]],
    current_columns: dict[str, Sequence[float]],
    *,
    bins: int = 10,
) -> dict[str, float]:
    """Calculate PSI for all overlapping feature names."""
    shared = sorted(set(reference_columns) & set(current_columns))
    return {
        name: population_stability_index(
            reference_columns[name],
            current_columns[name],
            bins=bins,
        )
        for name in shared
        if reference_columns[name] and current_columns[name]
    }
