"""Tests for dated NSE Security Master observations."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)


OBSERVED_ON = date(2026, 9, 4)


def make_record() -> NSESecurityMasterRecord:
    return NSESecurityMasterRecord(
        snapshot_date=OBSERVED_ON,
        fin_instrm_id="2885",
        symbol="RELIANCE",
        series="EQ",
        isin="INE002A01018",
    )


def test_observation_preserves_dated_identity() -> None:
    observation = NSESecurityMasterObservation.from_record(
        make_record()
    )

    assert observation.observed_on == OBSERVED_ON
    assert observation.fin_instrm_id == "2885"
    assert observation.symbol == "RELIANCE"
    assert observation.series == "EQ"
    assert observation.isin == "INE002A01018"
    assert observation.exchange == "NSE"


def test_observation_normalizes_identity_fields() -> None:
    observation = NSESecurityMasterObservation(
        observed_on=OBSERVED_ON,
        fin_instrm_id=" 2885 ",
        symbol=" reliance ",
        series=" eq ",
        isin=" ine002a01018 ",
        exchange=" nse ",
    )

    assert observation.fin_instrm_id == "2885"
    assert observation.symbol == "RELIANCE"
    assert observation.series == "EQ"
    assert observation.isin == "INE002A01018"
    assert observation.exchange == "NSE"


def test_observation_is_immutable() -> None:
    observation = NSESecurityMasterObservation.from_record(
        make_record()
    )

    with pytest.raises(FrozenInstanceError):
        observation.symbol = "TCS"  # type: ignore[misc]


def test_observation_rejects_datetime() -> None:
    with pytest.raises(TypeError):
        NSESecurityMasterObservation(
            observed_on=__import__("datetime").datetime(
                2026,
                9,
                4,
            ),
            fin_instrm_id="2885",
            symbol="RELIANCE",
            series="EQ",
            isin="INE002A01018",
        )


def test_observation_rejects_empty_identity_fields() -> None:
    with pytest.raises(ValueError):
        NSESecurityMasterObservation(
            observed_on=OBSERVED_ON,
            fin_instrm_id="",
            symbol="RELIANCE",
            series="EQ",
            isin="INE002A01018",
        )


def test_observation_rejects_wrong_record_type() -> None:
    with pytest.raises(TypeError):
        NSESecurityMasterObservation.from_record(
            object()  # type: ignore[arg-type]
        )


def test_observation_does_not_expose_effective_from() -> None:
    observation = NSESecurityMasterObservation.from_record(
        make_record()
    )

    assert hasattr(observation, "observed_on")
    assert not hasattr(observation, "effective_from")
