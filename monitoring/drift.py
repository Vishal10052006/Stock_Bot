from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True, slots=True)
class DriftReport:
    """Immutable distribution-drift measurement."""
    metric: str
    psi: float
    reference_count: int
    current_count: int
    status: str

    def __post_init__(self) -> None:
        if not self.metric.strip() or math.isnan(float(self.psi)) or self.psi < 0:
            raise ValueError("invalid drift report")
        if self.reference_count <= 0 or self.current_count <= 0:
            raise ValueError("sample counts must be positive")
        if self.status not in {"OK", "WARNING", "CRITICAL"}:
            raise ValueError("invalid drift status")

def _clean(values: list[float]) -> list[float]:
    if not values:
        raise ValueError("sample must be non-empty")
    cleaned = [float(v) for v in values]
    if not all(math.isfinite(v) for v in cleaned):
        raise ValueError("samples must be finite")
    return cleaned

def calculate_psi(reference: list[float], current: list[float], *, bins: int = 10, epsilon: float = 1e-6) -> float:
    """Calculate PSI using bins derived only from the reference sample."""
    ref = _clean(reference)
    cur = _clean(current)
    if bins < 2 or epsilon <= 0:
        raise ValueError("invalid PSI parameters")
    low, high = min(ref), max(ref)
    if high == low:
        # A constant reference distribution has no finite bin width. Treat
        # equality with the reference point as the dominant bucket and apply
        # epsilon smoothing so PSI remains finite and persistable.
        same_fraction = sum(v == low for v in cur) / len(cur)
        reference_same = 1.0 - epsilon
        reference_other = epsilon
        current_same = min(max(same_fraction, epsilon), 1.0 - epsilon)
        current_other = 1.0 - current_same
        return float(
            (current_same - reference_same) * math.log(current_same / reference_same)
            + (current_other - reference_other) * math.log(current_other / reference_other)
        )
    width = (high - low) / bins
    edges = [low + width * i for i in range(bins + 1)]
    def dist(values: list[float]) -> list[float]:
        counts = [0] * bins
        for value in values:
            if value < edges[0]:
                index = 0
            elif value >= edges[-1]:
                index = bins - 1
            else:
                index = min(int((value - low) / width), bins - 1)
            counts[index] += 1
        total = len(values)
        return [max(c / total, epsilon) for c in counts]
    r, c = dist(ref), dist(cur)
    return float(sum((cp - rp) * math.log(cp / rp) for rp, cp in zip(r, c)))
