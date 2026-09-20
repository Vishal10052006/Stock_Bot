"""Production distribution-drift monitoring."""
from __future__ import annotations
import math


def population_stability_index(reference: list[float], current: list[float], bins: int = 10) -> float:
    if not reference or not current:
        raise ValueError("reference and current samples must be non-empty")
    low, high = min(min(reference), min(current)), max(max(reference), max(current))
    if high == low:
        return 0.0
    edges = [low + (high - low) * i / bins for i in range(bins + 1)]

    def dist(values):
        counts = [0] * bins
        for value in values:
            index = next((i for i in range(bins) if edges[i] <= value < edges[i + 1]), bins - 1)
            counts[min(index, bins - 1)] += 1
        return [(count / len(values)) if count else 1e-6 for count in counts]

    ref, cur = dist(reference), dist(current)
    return sum((c - r) * math.log(c / r) for r, c in zip(ref, cur))
