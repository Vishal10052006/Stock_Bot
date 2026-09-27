"""Distribution-drift algorithms used by the monitoring engine."""

from __future__ import annotations

import math
from typing import Sequence


def population_stability_index(
    reference: Sequence[float],
    current: Sequence[float],
    *,
    bins: int = 10,
) -> float:
    """Calculate PSI using common deterministic bins.

    A single bin range is derived from both samples. Empty bins receive a
    small epsilon to keep the logarithm defined.
    """
    if not reference or not current:
        raise ValueError("reference and current samples must be non-empty")
    if bins < 2:
        raise ValueError("bins must be >= 2")

    values = [float(v) for v in (*reference, *current)]
    if any(not math.isfinite(v) for v in values):
        raise ValueError("drift samples must contain finite values")

    low = min(values)
    high = max(values)
    if high == low:
        return 0.0

    width = (high - low) / bins
    edges = [low + width * i for i in range(bins + 1)]

    def distribution(sample: Sequence[float]) -> list[float]:
        counts = [0] * bins
        for value in sample:
            index = min(int((value - low) / width), bins - 1)
            counts[index] += 1
        epsilon = 1e-6
        return [
            max(count / len(sample), epsilon)
            for count in counts
        ]

    reference_distribution = distribution(reference)
    current_distribution = distribution(current)

    return sum(
        (current_value - reference_value)
        * math.log(current_value / reference_value)
        for reference_value, current_value in zip(
            reference_distribution,
            current_distribution,
        )
    )


def mean_absolute_shift(reference: Sequence[float], current: Sequence[float]) -> float:
    """Return the absolute difference between sample means."""
    if not reference or not current:
        raise ValueError("reference and current samples must be non-empty")
    return abs(
        (sum(reference) / len(reference))
        - (sum(current) / len(current))
    )
