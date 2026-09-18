"""NSE CM Bhavcopy adapter for historical daily liquidity.

The adapter operates at DATE level rather than SYMBOL level.

The NSE CM Bhavcopy contains security-wise traded value for the entire
market session, allowing point-in-time liquidity construction without
one HTTP request per security.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path
import zipfile

import pandas as pd
import requests


class NSEBhavcopyDataError(RuntimeError):
    """Raised when NSE Bhavcopy data cannot be acquired or parsed."""


@dataclass(frozen=True, slots=True)
class NSEBhavcopyRow:
    """One equity-series Bhavcopy liquidity observation."""

    session_date: date
    fin_instrm_id: str
    isin: str
    symbol: str
    series: str
    traded_value: float


class NSEBhavcopyAdapter:
    """Download and parse NSE CM UDiFF Bhavcopy archives."""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        base_url: str = (
            "https://nsearchives.nseindia.com/content/cm"
        ),
        cache_dir: str | Path = "data/reference/nse/bhavcopy",
        session: requests.Session | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self._timeout = float(timeout)
        self._base_url = base_url.rstrip("/")
        self._cache_dir = Path(cache_dir)
        self._session = session or requests.Session()

    @staticmethod
    def _filename(session_date: date) -> str:
        return (
            "BhavCopy_NSE_CM_0_0_0_"
            f"{session_date:%Y%m%d}_F_0000.csv.zip"
        )

    def _url(self, session_date: date) -> str:
        return f"{self._base_url}/{self._filename(session_date)}"

    def _cache_path(self, session_date: date) -> Path:
        return self._cache_dir / self._filename(session_date)

    def _download(self, session_date: date) -> bytes:
        path = self._cache_path(session_date)

        if path.exists():
            payload = path.read_bytes()

            if payload:
                return payload

            path.unlink()

        self._cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            response = self._session.get(
                self._url(session_date),
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": (
                        "application/zip,"
                        "application/octet-stream,*/*"
                    ),
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NSEBhavcopyDataError(
                "NSE Bhavcopy request failed for "
                f"{session_date.isoformat()}"
            ) from exc

        payload = response.content

        if not payload:
            raise NSEBhavcopyDataError(
                "NSE Bhavcopy returned an empty payload for "
                f"{session_date.isoformat()}"
            )

        path.write_bytes(payload)

        return payload

    @staticmethod
    def _parse(
        payload: bytes,
        *,
        session_date: date,
    ) -> tuple[NSEBhavcopyRow, ...]:
        if not isinstance(payload, bytes) or not payload:
            raise NSEBhavcopyDataError(
                "Bhavcopy payload must be non-empty bytes"
            )

        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                csv_names = tuple(
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".csv")
                )

                if len(csv_names) != 1:
                    raise NSEBhavcopyDataError(
                        "Bhavcopy archive must contain exactly one CSV"
                    )

                with archive.open(csv_names[0]) as handle:
                    frame = pd.read_csv(handle)
        except (
            zipfile.BadZipFile,
            OSError,
            ValueError,
            pd.errors.ParserError,
        ) as exc:
            raise NSEBhavcopyDataError(
                "NSE Bhavcopy archive could not be parsed"
            ) from exc

        required = (
            "TradDt",
            "FinInstrmId",
            "ISIN",
            "TckrSymb",
            "SctySrs",
            "TtlTrfVal",
        )

        missing = tuple(
            column
            for column in required
            if column not in frame.columns
        )

        if missing:
            raise NSEBhavcopyDataError(
                "NSE Bhavcopy missing required columns: "
                + ", ".join(missing)
            )

        frame = frame.loc[
            frame["SctySrs"]
            .astype(str)
            .str.strip()
            .str.upper()
            .eq("EQ")
        ].copy()

        rows: list[NSEBhavcopyRow] = []

        for record in frame.itertuples(index=False):
            values = record._asdict()

            symbol = str(values["TckrSymb"]).strip().upper()
            isin = str(values["ISIN"]).strip().upper()
            fin_instrm_id = str(values["FinInstrmId"]).strip()
            series = str(values["SctySrs"]).strip().upper()

            if (
                not symbol
                or symbol == "NAN"
                or not isin
                or isin == "NAN"
                or not fin_instrm_id
                or fin_instrm_id == "NAN"
            ):
                continue

            try:
                traded_value = float(values["TtlTrfVal"])
            except (TypeError, ValueError) as exc:
                raise NSEBhavcopyDataError(
                    "invalid TtlTrfVal for "
                    f"{symbol} on {session_date}"
                ) from exc

            if not pd.notna(traded_value):
                raise NSEBhavcopyDataError(
                    "missing TtlTrfVal for "
                    f"{symbol} on {session_date}"
                )

            if traded_value < 0:
                raise NSEBhavcopyDataError(
                    "negative TtlTrfVal for "
                    f"{symbol} on {session_date}"
                )

            rows.append(
                NSEBhavcopyRow(
                    session_date=session_date,
                    fin_instrm_id=fin_instrm_id,
                    isin=isin,
                    symbol=symbol,
                    series=series,
                    traded_value=traded_value,
                )
            )

        rows.sort(
            key=lambda row: (
                row.fin_instrm_id,
                row.symbol,
            )
        )

        seen: set[str] = set()

        for row in rows:
            if row.fin_instrm_id in seen:
                raise NSEBhavcopyDataError(
                    "duplicate FinInstrmId in Bhavcopy: "
                    f"{row.fin_instrm_id}"
                )
            seen.add(row.fin_instrm_id)

        return tuple(rows)

    def get_rows(
        self,
        session_date: date,
    ) -> tuple[NSEBhavcopyRow, ...]:
        """Return all NSE EQ Bhavcopy liquidity rows for one date."""
        if not isinstance(session_date, date):
            raise TypeError("session_date must be a date")

        payload = self._download(session_date)

        return self._parse(
            payload,
            session_date=session_date,
        )

    def get_rows_for_dates(
        self,
        session_dates: tuple[date, ...],
    ) -> tuple[NSEBhavcopyRow, ...]:
        """Return deterministic EQ rows for multiple trading dates."""
        normalized = tuple(sorted(set(session_dates)))

        if not normalized:
            return ()

        rows: list[NSEBhavcopyRow] = []

        for session_date in normalized:
            rows.extend(self.get_rows(session_date))

        return tuple(
            sorted(
                rows,
                key=lambda row: (
                    row.session_date,
                    row.fin_instrm_id,
                    row.symbol,
                ),
            )
        )
