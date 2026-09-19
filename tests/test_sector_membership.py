from __future__ import annotations

from datetime import date

import pytest

from market.data.context.models import SectorMapping
from market.data.context.sector_membership import (
    PointInTimeSectorMembershipProvider,
)


def test_resolve_uses_point_in_time_interval() -> None:
    provider = PointInTimeSectorMembershipProvider(
        (
            SectorMapping(
                symbol="ABC",
                sector_index_symbol="NIFTY_IT",
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 6, 30),
            ),
            SectorMapping(
                symbol="ABC",
                sector_index_symbol="NIFTY_SERVICES_SECTOR",
                effective_from=date(2026, 7, 1),
            ),
        )
    )

    assert provider.resolve(
        symbol="ABC",
        as_of=date(2026, 6, 30),
    ).sector_index_symbol == "NIFTY_IT"

    assert provider.resolve(
        symbol="ABC",
        as_of=date(2026, 7, 1),
    ).sector_index_symbol == "NIFTY_SERVICES_SECTOR"


def test_resolve_does_not_infer_missing_membership() -> None:
    provider = PointInTimeSectorMembershipProvider(
        (
            SectorMapping(
                symbol="ABC",
                sector_index_symbol="NIFTY_IT",
                effective_from=date(2026, 7, 1),
            ),
        )
    )

    result = provider.resolve(
        symbol="ABC",
        as_of=date(2026, 6, 30),
    )

    assert result.sector_index_symbol is None


def test_resolve_many_requires_complete_membership_by_default() -> None:
    provider = PointInTimeSectorMembershipProvider(
        (
            SectorMapping(
                symbol="ABC",
                sector_index_symbol="NIFTY_IT",
                effective_from=date(2026, 1, 1),
            ),
        )
    )

    with pytest.raises(ValueError, match="missing point-in-time sector membership"):
        provider.resolve_many(
            symbols=("ABC", "XYZ"),
            as_of=date(2026, 9, 11),
        )


def test_resolve_many_can_measure_missing_membership_explicitly() -> None:
    provider = PointInTimeSectorMembershipProvider(
        (
            SectorMapping(
                symbol="ABC",
                sector_index_symbol="NIFTY_IT",
                effective_from=date(2026, 1, 1),
            ),
        )
    )

    result = provider.resolve_many(
        symbols=("XYZ", "ABC"),
        as_of=date(2026, 9, 11),
        require_complete=False,
    )

    assert result[0].symbol == "ABC"
    assert result[0].sector_index_symbol == "NIFTY_IT"
    assert result[1].symbol == "XYZ"
    assert result[1].sector_index_symbol is None


def test_mappings_for_returns_only_active_mappings() -> None:
    provider = PointInTimeSectorMembershipProvider(
        (
            SectorMapping(
                symbol="ABC",
                sector_index_symbol="NIFTY_IT",
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 6, 30),
            ),
            SectorMapping(
                symbol="ABC",
                sector_index_symbol="NIFTY_SERVICES_SECTOR",
                effective_from=date(2026, 7, 1),
            ),
        )
    )

    result = provider.mappings_for(
        symbols=("ABC",),
        as_of=date(2026, 9, 11),
    )

    assert result == (
        SectorMapping(
            symbol="ABC",
            sector_index_symbol="NIFTY_SERVICES_SECTOR",
            effective_from=date(2026, 7, 1),
        ),
    )
