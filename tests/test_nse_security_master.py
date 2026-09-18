"""Tests for NSE dated Security Master identity contracts."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)


def test_security_master_record_normalizes_fields() -> None:
    record = NSESecurityMasterRecord(
        snapshot_date=date(2026, 9, 4),
        fin_instrm_id=" 15342 ",
        symbol=" shalpaints ",
        series=" eq ",
        isin=" ine849c01026 ",
        exchange=" nse ",
    )

    assert record.fin_instrm_id == "15342"
    assert record.symbol == "SHALPAINTS"
    assert record.series == "EQ"
    assert record.isin == "INE849C01026"
    assert record.exchange == "NSE"


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"fin_instrm_id": ""}, "fin_instrm_id"),
        ({"symbol": ""}, "symbol"),
        ({"series": ""}, "series"),
        ({"isin": ""}, "isin"),
        ({"exchange": ""}, "exchange"),
    ],
)
def test_security_master_record_rejects_invalid_values(
    kwargs: dict[str, object],
    error: str,
) -> None:
    with pytest.raises((TypeError, ValueError), match=error):
        NSESecurityMasterRecord(snapshot_date=date(2026, 9, 4),
  # type: ignore[arg-type]
            fin_instrm_id="15342",
            symbol="SHALPAINTS",
            series="EQ",
            isin="INE849C01026",
            **kwargs,
        )


def test_same_isin_can_represent_distinct_nse_instrument_records() -> None:
    old_record = NSESecurityMasterRecord(
        snapshot_date=date(2026, 9, 4),
        fin_instrm_id="3072",
        symbol="SHALMPAINT",
        series="EQ",
        isin="INE849C01026",
    )

    new_record = NSESecurityMasterRecord(
        snapshot_date=date(2026, 9, 4),
        fin_instrm_id="15342",
        symbol="SHALPAINTS",
        series="EQ",
        isin="INE849C01026",
    )

    assert old_record.isin == new_record.isin
    assert old_record.fin_instrm_id != new_record.fin_instrm_id
    assert old_record.symbol != new_record.symbol
    assert old_record != new_record


def test_security_master_record_is_immutable() -> None:
    record = NSESecurityMasterRecord(
        snapshot_date=date(2026, 9, 4),
        fin_instrm_id="15342",
        symbol="SHALPAINTS",
        series="EQ",
        isin="INE849C01026",
    )

    with pytest.raises(FrozenInstanceError):
        record.symbol = "OTHER"  # type: ignore[misc]
