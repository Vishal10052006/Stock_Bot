"""Official NSE historical corporate-announcement archive intake."""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor
import http.cookiejar

from research.corpus.archive import HistoricalArchiveRecord

NSE_BASE_URL = "https://www.nseindia.com"
NSE_CORPORATE_ANNOUNCEMENTS_API = f"{NSE_BASE_URL}/api/corporate-announcements"
NSE_SOURCE_REFERENCE = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"


class NSEHistoricalArchiveClient:
    """Download and parse NSE corporate announcements with source timestamps."""

    def __init__(self, *, user_agent: str = "Stock_Bot/1.0 historical-research-intake") -> None:
        self.user_agent = user_agent

    def download_csv(self, *, start: datetime, end: datetime, output_path: str | Path) -> Path:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        if end < start:
            raise ValueError("end cannot precede start")

        nse_start = start.astimezone(ZoneInfo("Asia/Kolkata"))
        nse_end = end.astimezone(ZoneInfo("Asia/Kolkata"))
        query = urlencode({
            "index": "equities",
            "from_date": nse_start.strftime("%d-%m-%Y"),
            "to_date": nse_end.strftime("%d-%m-%Y"),
            "csv": "true",
        })
        opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/csv,application/csv;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": NSE_SOURCE_REFERENCE,
        }
        opener.open(Request(NSE_BASE_URL, headers=headers), timeout=20).read()
        response = opener.open(
            Request(f"{NSE_CORPORATE_ANNOUNCEMENTS_API}?{query}", headers=headers),
            timeout=30,
        )
        payload = response.read()
        if not payload or payload.lstrip().startswith(b"<"):
            raise ValueError("NSE returned non-CSV content")

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return destination

    @staticmethod
    def parse_csv(
        path: str | Path,
        *,
        archived_at: datetime,
    ) -> tuple[HistoricalArchiveRecord, ...]:
        if archived_at.tzinfo is None or archived_at.utcoffset() is None:
            raise ValueError("archived_at must be timezone-aware")
        rows = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = {str(k).strip().lower(): str(v or "").strip() for k, v in row.items()}
                symbol = _first(normalized, "symbol", "nse symbol", "nse_symbol").upper()
                subject = _first(normalized, "subject", "title")
                details = _first(normalized, "details", "description", "content")
                published_text = _first(normalized, "broadcast date/time", "broadcast_datetime", "broadcast date")
                received_text = _first(
                    normalized,
                    "exchange received time",
                    "received time",
                    "received_time",
                    "receipt",
                )
                available_text = _first(
                    normalized,
                    "exchange dissemination time",
                    "dissemination time",
                    "dissemination_time",
                    "dissemination",
                )
                if not symbol or not published_text or not received_text or not available_text:
                    raise ValueError("NSE archive row is missing PIT timestamp fields")
                published_at = _parse_datetime(published_text)
                observed_at = _parse_datetime(received_text)
                available_at = _parse_datetime(available_text)
                external_id = _first(normalized, "id", "external_id", "attachment", "xbrl")
                if not external_id:
                    external_id = hashlib.sha256(
                        f"{symbol}|{published_at.isoformat()}|{subject}|{details}".encode("utf-8")
                    ).hexdigest()[:32]
                archive_id = hashlib.sha256(
                    f"nse-corporate-filings|{external_id}".encode("utf-8")
                ).hexdigest()[:32]
                content = "\n\n".join(part for part in (subject, details) if part).strip()
                rows.append(HistoricalArchiveRecord(
                    archive_id=archive_id,
                    source_id="nse-corporate-filings",
                    external_id=external_id,
                    title=subject or "NSE corporate announcement",
                    content=content or subject or "NSE corporate announcement",
                    published_at=published_at,
                    observed_at=observed_at,
                    available_at=available_at,
                    symbols=(symbol,),
                    archived_at=archived_at,
                    metadata={"source_reference": NSE_SOURCE_REFERENCE, "exchange": "NSE", "raw_fields": normalized},
                ))
        return tuple(rows)


def _first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if row.get(key):
            return row[key]
    return ""


def _parse_datetime(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%y %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        except ValueError:
            pass
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("NSE timestamp must be timezone-aware")
    return parsed
