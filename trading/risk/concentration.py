"""Optional symbol and sector concentration controls.

The frozen trading specification defines gross exposure but does not freeze
symbol- or sector-specific numeric caps. These controls are therefore
disabled by default and activate only when explicitly configured.
"""

from __future__ import annotations

from collections.abc import Mapping


def check_symbol_exposure(
    *,
    symbol: str,
    proposed_value: float,
    existing_by_symbol: Mapping[str, float],
    max_symbol_exposure_fraction: float | None,
    equity: float,
) -> bool:
    """Return True when symbol exposure is within configured policy."""
    if max_symbol_exposure_fraction is None:
        return True

    current = float(existing_by_symbol.get(symbol.upper(), 0.0))

    return (
        current + proposed_value
        <= equity * max_symbol_exposure_fraction + 1e-12
    )


def check_sector_exposure(
    *,
    sector: str | None,
    proposed_value: float,
    existing_by_sector: Mapping[str, float],
    max_sector_exposure_fraction: float | None,
    equity: float,
) -> bool:
    """Return True when sector exposure is within configured policy."""
    if max_sector_exposure_fraction is None or not sector:
        return True

    current = float(existing_by_sector.get(sector, 0.0))

    return (
        current + proposed_value
        <= equity * max_sector_exposure_fraction + 1e-12
    )
