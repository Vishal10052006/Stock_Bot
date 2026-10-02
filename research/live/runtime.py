"""Point-in-time live research runtime.

This module bridges the existing frozen Research Bot providers to live
decision timestamps. Providers remain responsible for source-native evidence;
the cache is responsible for retaining only timestamped evidence and exposing
causal snapshots. No strategy, risk, or execution authority is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Event, Lock, Thread
from typing import Callable, Sequence

from research.contracts import ResearchDocument
from research.integration.analysis_contract import ResearchAnalysisContext
from research.integration.context import ResearchContextBuilder
from research.intelligence.model import ResearchIntelligenceModel
from research.providers.base import ResearchProvider


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class LiveResearchCache:
    """Thread-safe in-memory cache of source documents.

    available_at is never rewritten. A document fetched after a decision
    timestamp must not become retrospectively available to that earlier
    decision.
    """

    providers: tuple[ResearchProvider, ...]
    retention: timedelta = timedelta(days=7)
    clock: Clock = _utc_now
    _documents: dict[tuple[str, str], ResearchDocument] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.providers:
            raise ValueError("at least one research provider is required")
        if self.retention <= timedelta(0):
            raise ValueError("retention must be positive")

    def refresh(
        self,
        *,
        symbols: Sequence[str],
        start: datetime,
        end: datetime,
    ) -> int:
        """Fetch provider evidence and add valid documents to the cache."""
        start_utc = _require_aware(start, "start")
        end_utc = _require_aware(end, "end")
        if start_utc > end_utc:
            raise ValueError("start must not be after end")

        normalized_symbols = tuple(
            symbol.strip().upper() for symbol in symbols if symbol.strip()
        )
        fetched: list[ResearchDocument] = []

        for provider in self.providers:
            documents = provider.fetch(
                symbols=normalized_symbols,
                start=start_utc,
                end=end_utc,
            )
            for document in documents:
                if not isinstance(document, ResearchDocument):
                    raise TypeError(
                        f"{provider.source_id} returned a non-ResearchDocument"
                    )
                if document.available_at > end_utc:
                    raise ValueError(
                        f"{document.document_id} is unavailable at requested end"
                    )
                fetched.append(document)

        with self._lock:
            for document in fetched:
                key = (document.source_id, document.external_id)
                existing = self._documents.get(key)
                if existing is None:
                    self._documents[key] = document
                elif existing.content_hash != document.content_hash:
                    if document.available_at >= existing.available_at:
                        self._documents[key] = document

            self._prune_locked(_require_aware(self.clock(), "clock"))

        return len(fetched)

    def snapshot(
        self,
        *,
        symbol: str,
        as_of: datetime,
    ) -> tuple[ResearchDocument, ...]:
        """Return only evidence available at or before as_of."""
        decision_time = _require_aware(as_of, "as_of")
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")

        with self._lock:
            documents = tuple(
                document
                for document in self._documents.values()
                if normalized_symbol in {
                    value.strip().upper() for value in document.symbols
                }
                and document.available_at <= decision_time
            )

        return tuple(
            sorted(
                documents,
                key=lambda document: (
                    document.available_at,
                    document.document_id,
                ),
            )
        )

    def build_context(
        self,
        *,
        symbol: str,
        as_of: datetime,
        context_builder: ResearchContextBuilder | None = None,
    ):
        """Build the frozen ResearchContext from a causal cache snapshot."""
        decision_time = _require_aware(as_of, "as_of")
        documents = self.snapshot(symbol=symbol, as_of=decision_time)
        builder = context_builder or ResearchContextBuilder()
        return builder.build(
            symbol=symbol.strip().upper(),
            as_of=decision_time,
            documents=documents,
        )

    def build_analysis_context(
        self,
        *,
        symbol: str,
        as_of: datetime,
        context_builder: ResearchContextBuilder | None = None,
        intelligence_model: ResearchIntelligenceModel | None = None,
    ) -> ResearchAnalysisContext:
        """Build the stable RB-12.1 context at one causal decision time."""
        context = self.build_context(
            symbol=symbol,
            as_of=as_of,
            context_builder=context_builder,
        )
        intelligence = (
            intelligence_model or ResearchIntelligenceModel()
        ).score_context(context)
        return ResearchAnalysisContext.from_context(context, intelligence)

    def _prune_locked(self, now: datetime) -> None:
        cutoff = now - self.retention
        stale_keys = [
            key
            for key, document in self._documents.items()
            if document.available_at < cutoff
        ]
        for key in stale_keys:
            self._documents.pop(key, None)


@dataclass(slots=True)
class LiveResearchRuntime:
    """Optional background poller for live research evidence.

    Polling is separate from the market decision loop. A candle closing at T
    consumes only documents already captured with available_at <= T.
    """

    cache: LiveResearchCache
    symbols: tuple[str, ...]
    poll_interval: timedelta = timedelta(seconds=30)
    lookback: timedelta = timedelta(hours=24)
    clock: Clock = _utc_now
    _stop: Event = field(default_factory=Event, init=False, repr=False)
    _thread: Thread | None = field(default=None, init=False, repr=False)
    _last_error: Exception | None = field(default=None, init=False, repr=False)
    _last_refresh_at: datetime | None = field(default=None, init=False, repr=False)
    _refresh_count: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self.symbols = tuple(
            symbol.strip().upper() for symbol in self.symbols if symbol.strip()
        )
        if not self.symbols:
            raise ValueError("at least one live research symbol is required")
        if self.poll_interval <= timedelta(0):
            raise ValueError("poll_interval must be positive")
        if self.lookback <= timedelta(0):
            raise ValueError("lookback must be positive")

    @property
    def last_error(self) -> Exception | None:
        return self._last_error

    @property
    def last_refresh_at(self) -> datetime | None:
        return self._last_refresh_at

    @property
    def refresh_count(self) -> int:
        return self._refresh_count

    def refresh_once(self, *, now: datetime | None = None) -> int:
        """Perform one bounded provider refresh."""
        current = _require_aware(now or self.clock(), "now")
        count = self.cache.refresh(
            symbols=self.symbols,
            start=current - self.lookback,
            end=current,
        )
        self._last_refresh_at = current
        self._last_error = None
        self._refresh_count += 1
        return count

    def start(self, *, initial_refresh: bool = True) -> None:
        """Start the background polling loop once."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop.clear()
        if initial_refresh:
            try:
                self.refresh_once()
            except Exception as exc:
                self._last_error = exc

        self._thread = Thread(
            target=self._run,
            name="stock-bot-live-research",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, timeout: float = 5.0) -> None:
        """Stop polling without mutating cached evidence."""
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
        self._thread = None

    def _run(self) -> None:
        interval = self.poll_interval.total_seconds()
        while not self._stop.wait(interval):
            try:
                self.refresh_once()
            except Exception as exc:
                self._last_error = exc


__all__ = ["LiveResearchCache", "LiveResearchRuntime"]
