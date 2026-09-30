"""Process-local lock preventing concurrent automation runners."""

from __future__ import annotations

from threading import Lock


class AutomationLock:
    """Non-reentrant single-run lock."""

    def __init__(self) -> None:
        self._lock = Lock()

    def acquire(self, blocking: bool = False) -> bool:
        """Acquire the lock."""
        return self._lock.acquire(blocking=blocking)

    def release(self) -> None:
        """Release the lock."""
        self._lock.release()

    def __enter__(self) -> "AutomationLock":
        if not self.acquire():
            raise RuntimeError("automation run already active")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
