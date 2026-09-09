"""Tests for dated NSE Security Master snapshots."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime

import pytest

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_snapshot import (
    NSESecurityMasterSnapshot,
)


SNAPSHOT_DATE = date(2026, 9, 4)


def make_record(
    *,
    fin_instrm_id: str = "15342",
    symbol: str = "SHALPAINTS",
    series: str = "EQ",
    isin: str = "INE849C01026",
    snapshot_date: date = SNAPSHOT_DATE,
) -> NSESecurityMasterRecord:
    return NSESecurityMasterRecord(
        snapshot_date=snapshot_date,
        fin_instrm_id=fin_instrm_id,
        symbol=symbol,
        series=series,
        isin=isin,
    )


def test_snapshot_normalizes_and_sorts_records() -> None:
    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        records=(
            make_record(
                fin_instrm_id="2",
                symbol="TCS",
                isin="INE467B01029",
            ),
            make_record(
                fin_instrm_id="1",
                symbol="RELIANCE",
                isin="INE002A01018",
            ),
        ),
    )

    assert snapshot.snapshot_date == SNAPSHOT_DATE
    assert [record.symbol for record in snapshot.records] == [
        "RELIANCE",
        "TCS",
    ]


def test_snapshot_rejects_empty_records() -> None:
    with pytest.raises(ValueError, match="at least one"):
        NSESecurityMasterSnapshot(
            snapshot_date=SNAPSHOT_DATE,
            records=(),
        )


def test_snapshot_rejects_datetime() -> None:
    with pytest.raises(TypeError, match="snapshot_date"):
        NSESecurityMasterSnapshot(
            snapshot_date=datetime(2026, 9, 4),  # type: ignore[arg-type]
            records=(make_record(),),
        )


def test_snapshot_requires_matching_record_dates() -> None:
    with pytest.raises(ValueError, match="snapshot date"):
        NSESecurityMasterSnapshot(
            snapshot_date=SNAPSHOT_DATE,
            records=(
                make_record(
                    snapshot_date=date(2026, 9, 3),
                ),
            ),
        )


def test_snapshot_rejects_duplicate_fin_instrm_id() -> None:
    with pytest.raises(ValueError, match="FinInstrmId"):
        NSESecurityMasterSnapshot(
            snapshot_date=SNAPSHOT_DATE,
            records=(
                make_record(
                    fin_instrm_id="100",
                    symbol="RELIANCE",
                ),
                make_record(
                    fin_instrm_id="100",
                    symbol="TCS",
                    isin="INE467B01029",
                ),
            ),
        )


def test_snapshot_rejects_duplicate_symbol_series() -> None:
    with pytest.raises(ValueError, match=r"symbol, series"):
        NSESecurityMasterSnapshot(
            snapshot_date=SNAPSHOT_DATE,
            records=(
                make_record(
                    fin_instrm_id="100",
                    symbol="RELIANCE",
                ),
                make_record(
                    fin_instrm_id="101",
                    symbol="RELIANCE",
                    isin="INE467B01029",
                ),
            ),
        )


def test_snapshot_allows_duplicate_isin() -> None:
    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        records=(
            make_record(
                fin_instrm_id="1357",
                symbol="HIMADCHEM",
                isin="INE019C01026",
            ),
            make_record(
                fin_instrm_id="14334",
                symbol="HSCL",
                isin="INE019C01026",
            ),
        ),
    )

    assert snapshot.records[0].isin == snapshot.records[1].isin
    assert snapshot.records[0].fin_instrm_id != snapshot.records[1].fin_instrm_id


def test_record_for_resolves_symbol_and_series() -> None:
    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        records=(
            make_record(
                fin_instrm_id="3072",
                symbol="SHALMPAINT",
            ),
            make_record(
                fin_instrm_id="15342",
                symbol="SHALPAINTS",
            ),
        ),
    )

    record = snapshot.record_for(" shalpaints ", " eq ")

    assert record is not None
    assert record.fin_instrm_id == "15342"


def test_record_by_fin_instrm_id_resolves_exact_record() -> None:
    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        records=(
            make_record(
                fin_instrm_id="3072",
                symbol="SHALMPAINT",
            ),
            make_record(
                fin_instrm_id="15342",
                symbol="SHALPAINTS",
            ),
        ),
    )

    record = snapshot.record_by_fin_instrm_id(" 3072 ")

    assert record is not None
    assert record.symbol == "SHALMPAINT"


def test_snapshot_lookup_returns_none_when_missing() -> None:
    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        records=(make_record(),),
    )

    assert snapshot.record_for("UNKNOWN") is None
    assert snapshot.record_by_fin_instrm_id("999999") is None


def test_snapshot_is_immutable() -> None:
    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        records=(make_record(),),
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.records = ()  # type: ignore[misc]


def test_snapshot_observations_convert_all_records() -> None:
    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        records=(
            make_record(
                fin_instrm_id="3072",
                symbol="SHALMPAINT",
            ),
            make_record(
                fin_instrm_id="15342",
                symbol="SHALPAINTS",
            ),
        ),
    )

    observations = snapshot.observations()

    assert isinstance(observations, tuple)
    assert len(observations) == 2

    assert observations[0].observed_on == SNAPSHOT_DATE
    assert observations[0].fin_instrm_id == "3072"
    assert observations[0].symbol == "SHALMPAINT"

    assert observations[1].observed_on == SNAPSHOT_DATE
    assert observations[1].fin_instrm_id == "15342"
    assert observations[1].symbol == "SHALPAINTS"


def test_snapshot_observations_do_not_infer_effective_dates() -> None:
    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        records=(make_record(),),
    )

    observation = snapshot.observations()[0]

    assert observation.observed_on == SNAPSHOT_DATE
    assert not hasattr(observation, "effective_from")
    assert not hasattr(observation, "effective_to")


def test_snapshot_observations_are_deterministic() -> None:
    snapshot = NSESecurityMasterSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        records=(
            make_record(
                fin_instrm_id="2",
                symbol="TCS",
                isin="INE467B01029",
            ),
            make_record(
                fin_instrm_id="1",
                symbol="RELIANCE",
                isin="INE002A01018",
            ),
        ),
    )

    first = snapshot.observations()
    second = snapshot.observations()

    assert first == second
