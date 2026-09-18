"""Tests for complete dated NSE Security Master evidence snapshots."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime

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


SNAPSHOT_DATE = date(2026, 9, 4)


def make_evidence(
    *,
    fin_instrm_id: str,
    symbol: str,
    isin: str,
    snapshot_date: date = SNAPSHOT_DATE,
) -> NSESecurityMasterEvidence:
    return NSESecurityMasterEvidence(
        identity=NSESecurityMasterRecord(
            snapshot_date=snapshot_date,
            fin_instrm_id=fin_instrm_id,
            symbol=symbol,
            series="EQ",
            isin=isin,
        ),
        lifecycle=NSESecurityMasterLifecycle(
            listing_date=date(1998, 3, 4),
            removal_date=None,
            readmission_date=None,
            normal_market_status="1",
            normal_market_eligibility="0",
            deletion_flag="N",
        ),
    )


def test_snapshot_normalizes_and_sorts_evidence() -> None:
    snapshot = NSESecurityMasterEvidenceSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        evidence=(
            make_evidence(
                fin_instrm_id="2",
                symbol="TCS",
                isin="INE467B01029",
            ),
            make_evidence(
                fin_instrm_id="1",
                symbol="RELIANCE",
                isin="INE002A01018",
            ),
        ),
    )

    assert snapshot.snapshot_date == SNAPSHOT_DATE
    assert [
        item.identity.symbol
        for item in snapshot.evidence
    ] == ["RELIANCE", "TCS"]


def test_snapshot_rejects_empty_evidence() -> None:
    with pytest.raises(ValueError, match="at least one"):
        NSESecurityMasterEvidenceSnapshot(
            snapshot_date=SNAPSHOT_DATE,
            evidence=(),
        )


def test_snapshot_rejects_datetime() -> None:
    with pytest.raises(TypeError, match="snapshot_date"):
        NSESecurityMasterEvidenceSnapshot(
            snapshot_date=datetime(2026, 9, 4),  # type: ignore[arg-type]
            evidence=(make_evidence(
                fin_instrm_id="1",
                symbol="RELIANCE",
                isin="INE002A01018",
            ),),
        )


def test_snapshot_requires_matching_dates() -> None:
    with pytest.raises(ValueError, match="snapshot date"):
        NSESecurityMasterEvidenceSnapshot(
            snapshot_date=SNAPSHOT_DATE,
            evidence=(
                make_evidence(
                    fin_instrm_id="1",
                    symbol="RELIANCE",
                    isin="INE002A01018",
                    snapshot_date=date(2026, 9, 3),
                ),
            ),
        )


def test_snapshot_rejects_duplicate_fin_instrm_id() -> None:
    with pytest.raises(ValueError, match="FinInstrmId"):
        NSESecurityMasterEvidenceSnapshot(
            snapshot_date=SNAPSHOT_DATE,
            evidence=(
                make_evidence(
                    fin_instrm_id="100",
                    symbol="RELIANCE",
                    isin="INE002A01018",
                ),
                make_evidence(
                    fin_instrm_id="100",
                    symbol="TCS",
                    isin="INE467B01029",
                ),
            ),
        )


def test_snapshot_rejects_duplicate_symbol_series() -> None:
    with pytest.raises(ValueError, match=r"symbol, series"):
        NSESecurityMasterEvidenceSnapshot(
            snapshot_date=SNAPSHOT_DATE,
            evidence=(
                make_evidence(
                    fin_instrm_id="100",
                    symbol="RELIANCE",
                    isin="INE002A01018",
                ),
                make_evidence(
                    fin_instrm_id="101",
                    symbol="RELIANCE",
                    isin="INE467B01029",
                ),
            ),
        )


def test_snapshot_allows_duplicate_isin() -> None:
    snapshot = NSESecurityMasterEvidenceSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        evidence=(
            make_evidence(
                fin_instrm_id="1357",
                symbol="HIMADCHEM",
                isin="INE019C01026",
            ),
            make_evidence(
                fin_instrm_id="14334",
                symbol="HSCL",
                isin="INE019C01026",
            ),
        ),
    )

    assert (
        snapshot.evidence[0].identity.isin
        == snapshot.evidence[1].identity.isin
    )


def test_evidence_for_resolves_symbol_and_series() -> None:
    snapshot = NSESecurityMasterEvidenceSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        evidence=(
            make_evidence(
                fin_instrm_id="15342",
                symbol="SHALPAINTS",
                isin="INE849C01026",
            ),
        ),
    )

    result = snapshot.evidence_for(
        " shalpaints ",
        " eq ",
    )

    assert result is not None
    assert result.identity.fin_instrm_id == "15342"
    assert result.lifecycle.deletion_flag == "N"


def test_evidence_by_fin_instrm_id_resolves_exact_record() -> None:
    snapshot = NSESecurityMasterEvidenceSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        evidence=(
            make_evidence(
                fin_instrm_id="3072",
                symbol="SHALMPAINT",
                isin="INE849C01026",
            ),
        ),
    )

    result = snapshot.evidence_by_fin_instrm_id(" 3072 ")

    assert result is not None
    assert result.identity.symbol == "SHALMPAINT"


def test_snapshot_observations_are_explicit_identity_projection() -> None:
    snapshot = NSESecurityMasterEvidenceSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        evidence=(
            make_evidence(
                fin_instrm_id="15342",
                symbol="SHALPAINTS",
                isin="INE849C01026",
            ),
        ),
    )

    observations = snapshot.observations()

    assert len(observations) == 1
    assert observations[0].symbol == "SHALPAINTS"
    assert observations[0].observed_on == SNAPSHOT_DATE
    assert not hasattr(observations[0], "effective_from")


def test_snapshot_is_immutable() -> None:
    snapshot = NSESecurityMasterEvidenceSnapshot(
        snapshot_date=SNAPSHOT_DATE,
        evidence=(
            make_evidence(
                fin_instrm_id="15342",
                symbol="SHALPAINTS",
                isin="INE849C01026",
            ),
        ),
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.evidence = ()  # type: ignore[misc]
