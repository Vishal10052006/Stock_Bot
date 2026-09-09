"""NSE Security Master archive adapter."""

from __future__ import annotations

from datetime import date, datetime

import requests

from market.data.historical.nse_security_master_evidence_file_parser import (
    NSESecurityMasterEvidenceFileParseError,
    parse_nse_security_master_evidence_gzip,
)
from market.data.historical.nse_security_master_evidence_snapshot import (
    NSESecurityMasterEvidenceSnapshot,
)
from market.data.historical.nse_security_master_file_parser import (
    NSESecurityMasterFileParseError,
    parse_nse_security_master_gzip,
)
from market.data.historical.nse_security_master_snapshot import (
    NSESecurityMasterSnapshot,
)


class NSESecurityMasterDataError(RuntimeError):
    """Raised when the NSE Security Master cannot be retrieved or parsed."""


class NSESecurityMasterAdapter:
    """Retrieve dated NSE Security Master archive snapshots."""

    DEFAULT_BASE_URL = (
        "https://nsearchives.nseindia.com/content/cm"
    )
    DEFAULT_SESSION_URL = (
        "https://www.nseindia.com/report-detail/eq_security"
    )
    DEFAULT_REFERER = (
        "https://www.nseindia.com/report-detail/eq_security"
    )
    DEFAULT_TIMEOUT_SECONDS = 10.0

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        base_url: str = DEFAULT_BASE_URL,
        session: requests.Session | None = None,
    ) -> None:
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "timeout_seconds must be a positive number"
            )

        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty string")

        self._timeout_seconds = float(timeout_seconds)
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()

    def get_snapshot(
        self,
        snapshot_date: date,
    ) -> NSESecurityMasterSnapshot:
        """Fetch and parse one dated NSE Security Master snapshot."""

        self._validate_snapshot_date(snapshot_date)

        filename = (
            f"NSE_CM_security_{snapshot_date:%d%m%Y}.csv.gz"
        )
        url = f"{self._base_url}/{filename}"

        self._establish_session()

        try:
            response = self._session.get(
                url,
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NSESecurityMasterDataError(
                "NSE Security Master request failed"
            ) from exc

        payload = response.content

        if not isinstance(payload, bytes) or not payload:
            raise NSESecurityMasterDataError(
                "NSE Security Master returned an empty payload"
            )

        try:
            return parse_nse_security_master_gzip(
                payload,
                snapshot_date=snapshot_date,
            )
        except (TypeError, ValueError) as exc:
            raise NSESecurityMasterDataError(
                "NSE Security Master payload could not be parsed"
            ) from exc

    def get_evidence_snapshot(
        self,
        snapshot_date: date,
    ) -> NSESecurityMasterEvidenceSnapshot:
        """Fetch complete dated NSE Security Master evidence.

        Unlike ``get_snapshot()``, this preserves both identity and the
        raw NSE lifecycle fields required for historical lineage work.
        """

        self._validate_snapshot_date(snapshot_date)

        filename = (
            f"NSE_CM_security_{snapshot_date:%d%m%Y}.csv.gz"
        )
        url = f"{self._base_url}/{filename}"

        self._establish_session()

        try:
            response = self._session.get(
                url,
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NSESecurityMasterDataError(
                "NSE Security Master evidence request failed"
            ) from exc

        payload = response.content

        if not isinstance(payload, bytes) or not payload:
            raise NSESecurityMasterDataError(
                "NSE Security Master evidence returned an empty payload"
            )

        try:
            return parse_nse_security_master_evidence_gzip(
                payload,
                snapshot_date=snapshot_date,
            )
        except (
            TypeError,
            ValueError,
            NSESecurityMasterEvidenceFileParseError,
        ) as exc:
            raise NSESecurityMasterDataError(
                "NSE Security Master evidence payload could not be parsed"
            ) from exc

    def _establish_session(self) -> None:
        """Establish NSE cookies before requesting the archive."""

        try:
            response = self._session.get(
                self.DEFAULT_SESSION_URL,
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except Exception as exc:
            raise NSESecurityMasterDataError(
                "NSE Security Master session establishment failed"
            ) from exc

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0",
            "Accept": (
                "application/json,text/plain,*/*"
            ),
            "Referer": self.DEFAULT_REFERER,
        }

    @staticmethod
    def _validate_snapshot_date(snapshot_date: date) -> None:
        if not isinstance(snapshot_date, date):
            raise TypeError("snapshot_date must be a date")

        if isinstance(snapshot_date, datetime):
            raise TypeError("snapshot_date must be a date")
