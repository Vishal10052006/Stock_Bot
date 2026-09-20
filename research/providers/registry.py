"""Versioned Research Bot provider registry."""
from __future__ import annotations

from .base import ResearchProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ResearchProvider] = {}

    def register(self, provider: ResearchProvider) -> None:
        if provider.source_id in self._providers:
            raise ValueError(f"provider already registered: {provider.source_id}")
        self._providers[provider.source_id] = provider

    def get(self, source_id: str) -> ResearchProvider:
        try:
            return self._providers[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown research provider: {source_id}") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
