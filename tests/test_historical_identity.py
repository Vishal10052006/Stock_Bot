"""Tests for provider-neutral historical instrument identity."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from market.data.historical.identity import InstrumentIdentity


def test_identity_normalizes_values() -> None:
    identity = InstrumentIdentity(
        isin=" ine002a01018 ",
        symbol=" reliance ",
        exchange=" nse ",
    )

    assert identity.isin == "INE002A01018"
    assert identity.symbol == "RELIANCE"
    assert identity.exchange == "NSE"


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        (
            {"isin": "", "symbol": "RELIANCE"},
            "isin",
        ),
        (
            {"isin": "INE002A01018", "symbol": ""},
            "symbol",
        ),
        (
            {"isin": "INE002A01018", "symbol": "RELIANCE", "exchange": ""},
            "exchange",
        ),
    ],
)
def test_identity_rejects_empty_values(
    kwargs: dict[str, str],
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        InstrumentIdentity(**kwargs)


def test_identity_is_immutable() -> None:
    identity = InstrumentIdentity(
        isin="INE002A01018",
        symbol="RELIANCE",
    )

    with pytest.raises(FrozenInstanceError):
        identity.symbol = "OTHER"  # type: ignore[misc]


def test_same_isin_with_changed_symbol_represents_same_security() -> None:
    before = InstrumentIdentity(
        isin="INE002A01018",
        symbol="OLDNAME",
    )
    after = InstrumentIdentity(
        isin="INE002A01018",
        symbol="NEWNAME",
    )

    assert before.isin == after.isin
    assert before.symbol != after.symbol


def test_same_symbol_with_different_isin_represents_different_securities() -> None:
    first = InstrumentIdentity(
        isin="INE002A01018",
        symbol="ABC",
    )
    second = InstrumentIdentity(
        isin="INE467B01029",
        symbol="ABC",
    )

    assert first.symbol == second.symbol
    assert first.isin != second.isin


def test_identity_defaults_to_nse() -> None:
    identity = InstrumentIdentity(
        isin="INE002A01018",
        symbol="RELIANCE",
    )

    assert identity.exchange == "NSE"


def test_nse_instrument_identity_normalizes_values() -> None:
    from market.data.historical.nse_security_master import NSESecurityMasterRecord

    identity = NSESecurityMasterRecord(
        snapshot_date=date(2026, 9, 4),
        fin_instrm_id=" 15342 ",
        symbol=" shalpaints ",
        series=" eq ",
        isin=" ine849c01026 ",
        exchange=" nse ",
    )

    assert identity.fin_instrm_id == "15342"
    assert identity.symbol == "SHALPAINTS"
    assert identity.series == "EQ"
    assert identity.isin == "INE849C01026"
    assert identity.exchange == "NSE"


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
def test_nse_instrument_identity_rejects_empty_values(
    kwargs: dict[str, str],
    error: str,
) -> None:
    from market.data.historical.nse_security_master import NSESecurityMasterRecord

    defaults = {
        "snapshot_date": date(2026, 9, 4),
        "fin_instrm_id": "15342",
        "symbol": "SHALPAINTS",
        "series": "EQ",
        "isin": "INE849C01026",
        "exchange": "NSE",
    }
    defaults.update(kwargs)

    with pytest.raises(ValueError, match=error):
        NSESecurityMasterRecord(**defaults)


def test_nse_instrument_identity_distinguishes_same_isin_records() -> None:
    from market.data.historical.nse_security_master import NSESecurityMasterRecord

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


def test_nse_instrument_identity_is_immutable() -> None:
    from dataclasses import FrozenInstanceError

    from market.data.historical.nse_security_master import NSESecurityMasterRecord

    identity = NSESecurityMasterRecord(
        snapshot_date=date(2026, 9, 4),
        fin_instrm_id="15342",
        symbol="SHALPAINTS",
        series="EQ",
        isin="INE849C01026",
    )

    with pytest.raises(FrozenInstanceError):
        identity.symbol = "OTHER"  # type: ignore[misc]
