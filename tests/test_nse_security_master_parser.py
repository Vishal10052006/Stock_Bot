"""Tests for NSE Security Master record parsing."""

from datetime import date

import pytest

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_parser import (
    NSESecurityMasterParseError,
    parse_nse_security_master_record,
)


def raw_record(**overrides):
    record = {
        "FinInstrmId": "15342",
        "TckrSymb": "SHALPAINTS",
        "SctySrs": "EQ",
        "ISIN": "INE849C01026",
    }
    record.update(overrides)
    return record


def test_parser_returns_security_master_record():
    record = parse_nse_security_master_record(raw_record(), snapshot_date=date(2026, 9, 4))

    assert isinstance(record, NSESecurityMasterRecord)
    assert record.fin_instrm_id == "15342"
    assert record.symbol == "SHALPAINTS"
    assert record.series == "EQ"
    assert record.isin == "INE849C01026"
    assert record.exchange == "NSE"


def test_parser_normalizes_identity_fields():
    record = parse_nse_security_master_record(
        raw_record(
            FinInstrmId=" 15342 ",
            TckrSymb=" shalpaints ",
            SctySrs=" eq ",
            ISIN=" ine849c01026 ",
        ),
        snapshot_date=date(2026, 9, 4),
    )

    assert record.fin_instrm_id == "15342"
    assert record.symbol == "SHALPAINTS"
    assert record.series == "EQ"
    assert record.isin == "INE849C01026"


@pytest.mark.parametrize(
    "field",
    (
        "FinInstrmId",
        "TckrSymb",
        "SctySrs",
        "ISIN",
    ),
)
def test_parser_rejects_missing_required_field(field):
    record = raw_record()
    del record[field]

    with pytest.raises(
        NSESecurityMasterParseError,
        match="missing required fields",
    ):
        parse_nse_security_master_record(record, snapshot_date=date(2026, 9, 4))


@pytest.mark.parametrize(
    "field",
    (
        "FinInstrmId",
        "TckrSymb",
        "SctySrs",
        "ISIN",
    ),
)
def test_parser_rejects_empty_required_field(field):
    record = raw_record()
    record[field] = "   "

    with pytest.raises(
        NSESecurityMasterParseError,
        match="missing required fields",
    ):
        parse_nse_security_master_record(record, snapshot_date=date(2026, 9, 4))


def test_parser_rejects_non_mapping():
    with pytest.raises(
        NSESecurityMasterParseError,
        match="must be a mapping",
    ):
        parse_nse_security_master_record([], snapshot_date=date(2026, 9, 4))


def test_parser_preserves_distinct_instruments_with_same_isin():
    old_record = parse_nse_security_master_record(
        raw_record(
            FinInstrmId="3072",
            TckrSymb="SHALMPAINT",
        ),
        snapshot_date=date(2026, 9, 4),
    )

    new_record = parse_nse_security_master_record(
        raw_record(
            FinInstrmId="15342",
            TckrSymb="SHALPAINTS",
        ),
        snapshot_date=date(2026, 9, 4)
    )

    assert old_record.isin == new_record.isin
    assert old_record.fin_instrm_id != new_record.fin_instrm_id
    assert old_record.symbol != new_record.symbol


def test_parser_does_not_require_unique_isin():
    first = parse_nse_security_master_record(
        raw_record(
            FinInstrmId="1357",
            TckrSymb="HIMADCHEM",
            ISIN="INE019C01026",
        ),
        snapshot_date=date(2026, 9, 4)
    )

    second = parse_nse_security_master_record(
        raw_record(
            FinInstrmId="14334",
            TckrSymb="HSCL",
            ISIN="INE019C01026",
        ),
        snapshot_date=date(2026, 9, 4)
    )

    assert first.isin == second.isin
    assert first.fin_instrm_id != second.fin_instrm_id
