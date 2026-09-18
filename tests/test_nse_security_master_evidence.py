"""Tests for combined NSE Security Master evidence."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_evidence import (
    NSESecurityMasterEvidence,
)
from market.data.historical.nse_security_master_lifecycle import (
    NSESecurityMasterLifecycle,
)


SNAPSHOT_DATE = date(2026, 9, 4)


def make_identity() -> NSESecurityMasterRecord:
    return NSESecurityMasterRecord(
        snapshot_date=SNAPSHOT_DATE,
        fin_instrm_id="15342",
        symbol="SHALPAINTS",
        series="EQ",
        isin="INE849C01026",
    )


def make_lifecycle() -> NSESecurityMasterLifecycle:
    return NSESecurityMasterLifecycle(
        listing_date=date(1998, 3, 4),
        removal_date=None,
        readmission_date=None,
        normal_market_status="1",
        normal_market_eligibility="0",
        deletion_flag="N",
    )


def test_evidence_preserves_identity_and_lifecycle() -> None:
    identity = make_identity()
    lifecycle = make_lifecycle()

    evidence = NSESecurityMasterEvidence(
        identity=identity,
        lifecycle=lifecycle,
    )

    assert evidence.identity is identity
    assert evidence.lifecycle is lifecycle


def test_evidence_uses_fin_instrm_id_as_identity_anchor() -> None:
    identity = make_identity()
    lifecycle = make_lifecycle()

    evidence = NSESecurityMasterEvidence(
        identity=identity,
        lifecycle=lifecycle,
    )

    assert evidence.identity.fin_instrm_id == "15342"


def test_evidence_is_immutable() -> None:
    evidence = NSESecurityMasterEvidence(
        identity=make_identity(),
        lifecycle=make_lifecycle(),
    )

    with pytest.raises(FrozenInstanceError):
        evidence.identity = make_identity()  # type: ignore[misc]


@pytest.mark.parametrize(
    "field",
    ["identity", "lifecycle"],
)
def test_evidence_rejects_wrong_component_type(field: str) -> None:
    values = {
        "identity": make_identity(),
        "lifecycle": make_lifecycle(),
    }
    values[field] = object()

    with pytest.raises(TypeError, match=field):
        NSESecurityMasterEvidence(**values)
