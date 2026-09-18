"""Tests for the NSE Security Master archive adapter."""

from datetime import date, datetime
import gzip

import pytest
import requests

from market.data.historical.adapters.nse_security_master import (
    NSESecurityMasterAdapter,
    NSESecurityMasterDataError,
)


SNAPSHOT_DATE = date(2026, 9, 4)

CSV_PAYLOAD = (
    "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN\n"
    "2885,RELIANCE,EQ,RELIANCE INDUSTRIES LIMITED,"
    "INE002A01018\n"
).encode()

GZIP_PAYLOAD = gzip.compress(CSV_PAYLOAD)


class FakeResponse:
    def __init__(
        self,
        *,
        content: bytes,
        status_error: requests.HTTPError | None = None,
    ) -> None:
        self.content = content
        self._status_error = status_error

    def raise_for_status(self) -> None:
        if self._status_error is not None:
            raise self._status_error


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((url, kwargs))
        return self.response


def test_get_snapshot_builds_dated_snapshot() -> None:
    session = FakeSession(
        FakeResponse(content=GZIP_PAYLOAD)
    )

    adapter = NSESecurityMasterAdapter(
        session=session,
    )

    snapshot = adapter.get_snapshot(SNAPSHOT_DATE)

    assert snapshot.snapshot_date == SNAPSHOT_DATE
    assert len(snapshot.records) == 1
    assert snapshot.records[0].symbol == "RELIANCE"

    assert len(session.calls) == 2

    assert session.calls[0] == (
        "https://www.nseindia.com/report-detail/eq_security",
        {
            "headers": {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json,text/plain,*/*",
                "Referer": (
                    "https://www.nseindia.com/report-detail/eq_security"
                ),
            },
            "timeout": 10.0,
        },
    )

    assert session.calls[1] == (
        "https://nsearchives.nseindia.com/content/cm/"
        "NSE_CM_security_04092026.csv.gz",
        {
            "headers": {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json,text/plain,*/*",
                "Referer": (
                    "https://www.nseindia.com/report-detail/eq_security"
                ),
            },
            "timeout": 10.0,
        },
    )


def test_get_snapshot_uses_custom_base_url_and_timeout() -> None:
    session = FakeSession(
        FakeResponse(content=GZIP_PAYLOAD)
    )

    adapter = NSESecurityMasterAdapter(
        session=session,
        base_url="https://example.test/cm/",
        timeout_seconds=7,
    )

    adapter.get_snapshot(SNAPSHOT_DATE)

    assert session.calls[1] == (
        "https://example.test/cm/NSE_CM_security_04092026.csv.gz",
        {
            "headers": {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json,text/plain,*/*",
                "Referer": (
                    "https://www.nseindia.com/report-detail/eq_security"
                ),
            },
            "timeout": 7.0,
        },
    )


class ArchiveFailureSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((url, kwargs))

        if len(self.calls) == 1:
            return FakeResponse(content=b"session-ok")

        return FakeResponse(
            content=b"",
            status_error=requests.HTTPError("404"),
        )


def test_get_snapshot_wraps_archive_http_failure() -> None:
    session = ArchiveFailureSession()

    adapter = NSESecurityMasterAdapter(
        session=session,
    )

    with pytest.raises(
        NSESecurityMasterDataError,
        match="request failed",
    ):
        adapter.get_snapshot(SNAPSHOT_DATE)

    assert len(session.calls) == 2


class SessionFailureSession:
    def get(self, url: str, **kwargs: object) -> FakeResponse:
        return FakeResponse(
            content=b"",
            status_error=requests.HTTPError("session failure"),
        )


def test_get_snapshot_wraps_session_establishment_failure() -> None:
    adapter = NSESecurityMasterAdapter(
        session=SessionFailureSession(),
    )

    with pytest.raises(
        NSESecurityMasterDataError,
        match="session establishment failed",
    ):
        adapter.get_snapshot(SNAPSHOT_DATE)


def test_get_snapshot_rejects_empty_payload() -> None:
    session = FakeSession(
        FakeResponse(content=b"")
    )

    adapter = NSESecurityMasterAdapter(
        session=session,
    )

    with pytest.raises(
        NSESecurityMasterDataError,
        match="empty payload",
    ):
        adapter.get_snapshot(SNAPSHOT_DATE)


def test_get_snapshot_wraps_invalid_payload() -> None:
    session = FakeSession(
        FakeResponse(content=b"not-gzip")
    )

    adapter = NSESecurityMasterAdapter(
        session=session,
    )

    with pytest.raises(
        NSESecurityMasterDataError,
        match="could not be parsed",
    ):
        adapter.get_snapshot(SNAPSHOT_DATE)


@pytest.mark.parametrize(
    "snapshot_date",
    [
        datetime(2026, 9, 4),
        "2026-09-04",
        None,
    ],
)
def test_get_snapshot_rejects_invalid_snapshot_date(
    snapshot_date: object,
) -> None:
    session = FakeSession(
        FakeResponse(content=GZIP_PAYLOAD)
    )

    adapter = NSESecurityMasterAdapter(
        session=session,
    )

    with pytest.raises((TypeError,)):
        adapter.get_snapshot(snapshot_date)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "timeout",
    [
        0,
        -1,
        True,
        "10",
    ],
)
def test_adapter_rejects_invalid_timeout(timeout: object) -> None:
    with pytest.raises(ValueError):
        NSESecurityMasterAdapter(
            timeout_seconds=timeout,  # type: ignore[arg-type]
        )


def test_adapter_rejects_empty_base_url() -> None:
    with pytest.raises(ValueError):
        NSESecurityMasterAdapter(base_url=" ")


EVIDENCE_CSV_PAYLOAD = (
    "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,"
    "ListgDt,RmvlDt,RadmssnDt,SctyStsNrmlMkt,"
    "ElgbltyNrmlMkt,DelFlg\n"
    "15342,SHALPAINTS,EQ,SHALIMAR PAINTS LIMITED,"
    "INE849C01026,888969600,0,0,1,0,N\n"
)

EVIDENCE_GZIP_PAYLOAD = gzip.compress(EVIDENCE_CSV_PAYLOAD.encode())


def test_get_evidence_snapshot_preserves_identity_and_lifecycle() -> None:
    session = FakeSession(
        FakeResponse(content=EVIDENCE_GZIP_PAYLOAD)
    )

    adapter = NSESecurityMasterAdapter(
        session=session,
    )

    snapshot = adapter.get_evidence_snapshot(SNAPSHOT_DATE)

    assert snapshot.snapshot_date == SNAPSHOT_DATE
    assert len(snapshot.evidence) == 1

    evidence = snapshot.evidence[0]

    assert evidence.identity.fin_instrm_id == "15342"
    assert evidence.identity.symbol == "SHALPAINTS"
    assert evidence.identity.series == "EQ"
    assert evidence.identity.isin == "INE849C01026"

    assert evidence.lifecycle.listing_date == date(1998, 3, 4)
    assert evidence.lifecycle.removal_date is None
    assert evidence.lifecycle.readmission_date is None
    assert evidence.lifecycle.normal_market_status == "1"
    assert evidence.lifecycle.normal_market_eligibility == "0"
    assert evidence.lifecycle.deletion_flag == "N"

    assert session.calls[1][0] == (
        "https://nsearchives.nseindia.com/content/cm/"
        "NSE_CM_security_04092026.csv.gz"
    )


def test_get_evidence_snapshot_wraps_invalid_payload() -> None:
    session = FakeSession(
        FakeResponse(content=b"not-gzip")
    )

    adapter = NSESecurityMasterAdapter(
        session=session,
    )

    with pytest.raises(
        NSESecurityMasterDataError,
        match="evidence payload could not be parsed",
    ):
        adapter.get_evidence_snapshot(SNAPSHOT_DATE)

    assert len(session.calls) == 2


def test_get_evidence_snapshot_wraps_empty_payload() -> None:
    session = FakeSession(
        FakeResponse(content=b"")
    )

    adapter = NSESecurityMasterAdapter(
        session=session,
    )

    with pytest.raises(
        NSESecurityMasterDataError,
        match="evidence returned an empty payload",
    ):
        adapter.get_evidence_snapshot(SNAPSHOT_DATE)

    assert len(session.calls) == 2
