"""NSE corporate-filings CSV adapter.

NSE corporate-filings pages expose CSV downloads. This adapter consumes the
downloaded file and uses exchange dissemination time as the PIT boundary when
that field is present.
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from research.contracts import ResearchDocument


class NSECorporateCsvProvider:
    source_id = "nse-corporate-filings"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def fetch(self, *, symbols: tuple[str, ...] | list[str], start: datetime, end: datetime) -> tuple[ResearchDocument, ...]:
        wanted = {s.upper() for s in symbols}
        documents: list[ResearchDocument] = []

        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                normalized = {str(k).strip().lower(): str(v or "").strip() for k, v in row.items()}
                symbol = self._first(normalized, "symbol", "nse symbol", "nse_symbol").upper()
                if wanted and symbol not in wanted:
                    continue

                published_text = self._first(normalized, "broadcast date/time", "broadcast_datetime", "broadcast date", "date")
                if not published_text:
                    continue
                published_at = self._parse_datetime(published_text)
                if not start <= published_at <= end:
                    continue

                available_text = self._first(
                    normalized,
                    "dissemination time",
                    "dissemination_time",
                    "broadcast date/time",
                    "broadcast_datetime",
                )
                available_at = self._parse_datetime(available_text) if available_text else published_at
                title = self._first(normalized, "subject", "title") or "NSE corporate filing"
                details = self._first(normalized, "details", "description", "content")
                external_id = self._first(normalized, "id", "external_id", "attachment", "xbrl") or (
                    f"{symbol}|{title}|{published_at.isoformat()}"
                )
                now = datetime.now(timezone.utc)

                documents.append(
                    ResearchDocument(
                        document_id=sha256(f"{self.source_id}|{external_id}".encode()).hexdigest()[:32],
                        source_id=self.source_id,
                        external_id=external_id,
                        title=title,
                        content=details or title,
                        published_at=published_at,
                        observed_at=available_at,
                        processed_at=now,
                        available_at=available_at,
                        symbols=(symbol,) if symbol else (),
                        metadata={"exchange": "NSE", "raw_fields": normalized},
                    )
                )
        return tuple(documents)

    @staticmethod
    def _first(row: dict[str, str], *keys: str) -> str:
        for key in keys:
            if row.get(key):
                return row[key]
        return ""

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        value = value.strip()
        formats = (
            "%d-%b-%Y %H:%M:%S", "%d-%b-%y %H:%M:%S",
            "%d-%m-%Y %H:%M:%S", "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
        )
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
