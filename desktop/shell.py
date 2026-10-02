"""Dependency-free D00 desktop shell contract.

The shell owns navigation and application composition only. It does not
authorize trades, mutate strategy/risk state, submit orders, or bypass
existing authority boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Iterable


@dataclass(frozen=True, slots=True)
class DesktopView:
    """Immutable registration metadata for one desktop view."""

    view_id: str
    title: str
    order: int = 0

    def __post_init__(self) -> None:
        if not self.view_id.strip():
            raise ValueError("view_id must be non-empty")
        if not self.title.strip():
            raise ValueError("title must be non-empty")
        if self.order < 0:
            raise ValueError("order must be non-negative")


class DesktopShell:
    """Deterministic navigation/composition boundary for the desktop app."""

    def __init__(self, views: Iterable[DesktopView] = ()) -> None:
        self._lock = RLock()
        self._views: dict[str, DesktopView] = {}
        self._active_view_id: str | None = None
        for view in views:
            self.register_view(view)

    @property
    def active_view(self) -> DesktopView | None:
        with self._lock:
            if self._active_view_id is None:
                return None
            return self._views[self._active_view_id]

    @property
    def views(self) -> tuple[DesktopView, ...]:
        with self._lock:
            return tuple(sorted(self._views.values(), key=lambda item: (item.order, item.view_id)))

    def register_view(self, view: DesktopView) -> None:
        with self._lock:
            if view.view_id in self._views:
                raise ValueError(f"view already registered: {view.view_id}")
            self._views[view.view_id] = view
            if self._active_view_id is None:
                self._active_view_id = view.view_id

    def activate(self, view_id: str) -> DesktopView:
        with self._lock:
            if view_id not in self._views:
                raise KeyError(f"unknown desktop view: {view_id}")
            self._active_view_id = view_id
            return self._views[view_id]

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "active_view": self._active_view_id,
                "views": tuple(
                    {
                        "view_id": view.view_id,
                        "title": view.title,
                        "order": view.order,
                    }
                    for view in self.views
                ),
                "authority": "OBSERVATION_ONLY",
            }
