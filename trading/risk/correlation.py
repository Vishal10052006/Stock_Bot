"""Optional correlation-concentration controls.

The frozen trading specification does not define a numeric correlation
threshold/cap yet, so this policy is opt-in.
"""

from __future__ import annotations

from collections.abc import Mapping


def correlation_exposure_allowed(
    *,
    symbol: str,
    proposed_value: float,
    existing_by_symbol: Mapping[str, float],
    pairwise_correlation: Mapping[str, float],
    equity: float,
    minimum_abs_correlation: float | None,
    max_correlated_exposure_fraction: float | None,
) -> bool:
    """Check aggregate exposure to positions above the correlation threshold."""
    if (
        minimum_abs_correlation is None
        or max_correlated_exposure_fraction is None
    ):
        return True

    correlated_value = 0.0

    for other_symbol, exposure in existing_by_symbol.items():
        if other_symbol.upper() == symbol.upper():
            continue

        correlation = pairwise_correlation.get(other_symbol.upper())

        if (
            correlation is not None
            and abs(float(correlation)) >= minimum_abs_correlation
        ):
            correlated_value += float(exposure)

    return (
        correlated_value + proposed_value
        <= equity * max_correlated_exposure_fraction + 1e-12
    )
