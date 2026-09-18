"""Tests for dated NSE Security Master observation history."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_evidence import (
    NSESecurityMasterEvidence,
)
from market.data.historical.nse_security_master_evidence_snapshot import (
    NSESecurityMasterEvidenceSnapshot,
)
from market.data.historical.nse_security_master_lifecycle import (
    NSESecurityMasterLifecycle,
)
from market.data.historical.nse_security_master_observation_history import (
    NSESecurityMasterObservationHistory,
)


def make_snapshot(
    snapshot_date: date,
    *,
    symbol: str = "RELIANCE",
    fin_instrm_id: str = "2885",
    isin: str = "INE002A01018",
) -> NSESecurityMasterEvidenceSnapshot:
    evidence = NSESecurityMasterEvidence(
        identity=NSESecurityMasterRecord(
            snapshot_date=snapshot_date,
            fin_instrm_id=fin_instrm_id,
            symbol=symbol,
            series="EQ",
            isin=isin,
        ),
        lifecycle=NSESecurityMasterLifecycle(
            listing_date=date(1977, 1, 1),
            removal_date=None,
            readmission_date=None,
            normal_market_status="1",
            normal_market_eligibility="0",
            deletion_flag="N",
        ),
    )

    return NSESecurityMasterEvidenceSnapshot(
        snapshot_date=snapshot_date,
        evidence=(evidence,),
    )


def test_history_sorts_snapshots_chronologically() -> None:
    history = NSESecurityMasterObservationHistory(
        snapshots=(
            make_snapshot(date(2026, 9, 4)),
            make_snapshot(date(2026, 9, 2)),
            make_snapshot(date(2026, 9, 3)),
        ),
    )

    assert [
        snapshot.snapshot_date
        for snapshot in history.snapshots
    ] == [
        date(2026, 9, 2),
        date(2026, 9, 3),
        date(2026, 9, 4),
    ]

    assert history.start_date == date(2026, 9, 2)
    assert history.end_date == date(2026, 9, 4)


def test_history_flattens_observations_without_inventing_effective_dates() -> None:
    history = NSESecurityMasterObservationHistory(
        snapshots=(
            make_snapshot(
                date(2026, 9, 2),
                symbol="OLD",
                fin_instrm_id="100",
            ),
            make_snapshot(
                date(2026, 9, 3),
                symbol="NEW",
                fin_instrm_id="200",
            ),
        ),
    )

    observations = history.observations()

    assert len(observations) == 2
    assert observations[0].observed_on == date(2026, 9, 2)
    assert observations[0].symbol == "OLD"
    assert observations[1].observed_on == date(2026, 9, 3)
    assert observations[1].symbol == "NEW"

    assert not hasattr(observations[0], "effective_from")
    assert not hasattr(observations[0], "effective_to")


def test_history_filters_symbol_and_series() -> None:
    history = NSESecurityMasterObservationHistory(
        snapshots=(
            make_snapshot(
                date(2026, 9, 2),
                symbol="RELIANCE",
                fin_instrm_id="2885",
            ),
            make_snapshot(
                date(2026, 9, 3),
                symbol="TCS",
                fin_instrm_id="11536",
                isin="INE467B01029",
            ),
            make_snapshot(
                date(2026, 9, 4),
                symbol="RELIANCE",
                fin_instrm_id="2885",
            ),
        ),
    )

    observations = history.observations_for(
        " reliance ",
        " eq ",
    )

    assert len(observations) == 2
    assert [
        observation.observed_on
        for observation in observations
    ] == [
        date(2026, 9, 2),
        date(2026, 9, 4),
    ]


def test_history_rejects_empty_snapshots() -> None:
    with pytest.raises(ValueError, match="at least one"):
        NSESecurityMasterObservationHistory(snapshots=())


def test_history_rejects_wrong_snapshot_type() -> None:
    with pytest.raises(TypeError, match="snapshots\\[0\\]"):
        NSESecurityMasterObservationHistory(
            snapshots=(object(),),  # type: ignore[arg-type]
        )


def test_history_rejects_duplicate_snapshot_dates() -> None:
    snapshot = make_snapshot(date(2026, 9, 4))

    with pytest.raises(ValueError, match="snapshot dates"):
        NSESecurityMasterObservationHistory(
            snapshots=(snapshot, snapshot),
        )


def test_history_is_immutable() -> None:
    history = NSESecurityMasterObservationHistory(
        snapshots=(make_snapshot(date(2026, 9, 4)),),
    )

    with pytest.raises(FrozenInstanceError):
        history.snapshots = ()  # type: ignore[misc]


def test_history_observations_are_deterministic() -> None:
    history = NSESecurityMasterObservationHistory(
        snapshots=(
            make_snapshot(
                date(2026, 9, 4),
                symbol="TCS",
                fin_instrm_id="11536",
                isin="INE467B01029",
            ),
            make_snapshot(
                date(2026, 9, 2),
                symbol="RELIANCE",
                fin_instrm_id="2885",
            ),
        ),
    )

    assert history.observations() == history.observations()
