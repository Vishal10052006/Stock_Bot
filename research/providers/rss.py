"""Real RSS/Atom provider for point-in-time research ingestion.

References:
    RBI RSS: https://www.rbi.org.in/Scripts/rss.aspx
    PIB RSS: https://www.pib.gov.in/ViewRss.aspx
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from research.contracts import ResearchDocument


class RssResearchProvider:
    """Fetch RSS/Atom entries from a configured public source."""

    def __init__(self, source_id: str, url: str, timeout_seconds: float = 20.0) -> None:
        self.source_id = source_id
        self.url = url
        self.timeout_seconds = timeout_seconds

    def fetch(self, *, symbols: tuple[str, ...] | list[str], start: datetime, end: datetime) -> tuple[ResearchDocument, ...]:
        now = datetime.now(timezone.utc)
        request = Request(self.url, headers={"User-Agent": "STOCK_BOT-Research/1.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = response.read()

        root = ElementTree.fromstring(payload)
        documents: list[ResearchDocument] = []
        symbol_set = {s.upper() for s in symbols}

        for item in root.iter():
            title = self._child_text(item, "title")
            published_text = (
                self._child_text(item, "pubDate")
                or self._child_text(item, "published")
                or self._child_text(item, "updated")
            )
            if not title or not published_text:
                continue

            published_at = self._parse_datetime(published_text)
            if published_at < start or published_at > end:
                continue

            summary = self._child_text(item, "description") or self._child_text(item, "summary") or ""
            external_id = (
                self._child_text(item, "guid")
                or self._child_text(item, "id")
                or sha256(f"{self.url}|{title}|{published_at.isoformat()}".encode()).hexdigest()
            )
            text = f"{title}\n{summary}".strip()

            if symbol_set and not any(symbol in text.upper() for symbol in symbol_set):
                continue

            documents.append(
                ResearchDocument(
                    document_id=sha256(f"{self.source_id}|{external_id}".encode()).hexdigest()[:32],
                    source_id=self.source_id,
                    external_id=external_id,
                    title=title,
                    content=text,
                    published_at=published_at,
                    observed_at=now,
                    processed_at=now,
                    available_at=now,
                    symbols=tuple(sorted(symbol_set & set(self._extract_symbols(text, symbol_set)))),
                    metadata={"provider_url": self.url, "retrieved_at": now.isoformat()},
                )
            )
        return tuple(documents)

    @staticmethod
    def _child_text(element: ElementTree.Element, local_name: str) -> str:
        for child in list(element):
            if child.tag.rsplit("}", 1)[-1].lower() == local_name.lower():
                return "".join(child.itertext()).strip()
        return ""

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(value).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

    @staticmethod
    def _extract_symbols(text: str, candidates: set[str]) -> tuple[str, ...]:
        upper = text.upper()
        return tuple(symbol for symbol in candidates if symbol in upper)
