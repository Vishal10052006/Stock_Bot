"""Operator control plane for the real-market paper experiment.

This module owns lifecycle control only. It never calls a broker and never
bypasses Strategy -> Risk -> Safety -> Paper execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock, Thread
from typing import Callable, Any


class PaperControlState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    KILLED = "KILLED"


@dataclass(frozen=True, slots=True)
class PaperControlSnapshot:
    state: str
    target_trades: int
    predictions: int
    completed_trades: int
    net_pnl: float | None
    error: str | None
    broker_orders: int
    trading_authority: str


class PaperControlPlane:
    """Thread-safe lifecycle controller around one LiveModelRuntime instance."""

    def __init__(
        self,
        runtime_factory: Callable[[], Any],
        *,
        target_trades: int = 10,
    ) -> None:
        if target_trades < 1:
            raise ValueError("target_trades must be positive")
        self._runtime_factory = runtime_factory
        self._target_trades = target_trades
        self._lock = Lock()
        self._runtime: Any | None = None
        self._thread: Thread | None = None
        self._state = PaperControlState.STOPPED
        self._error: str | None = None
        self._kill_requested = False

    def _run(self) -> None:
        try:
            runtime = self._runtime
            if runtime is None:
                raise RuntimeError("runtime was not initialized")
            runtime.run()
            with self._lock:
                if self._kill_requested:
                    self._state = PaperControlState.KILLED
                elif runtime.paper_engine.session_completed:
                    self._state = PaperControlState.COMPLETED
                else:
                    self._state = PaperControlState.STOPPED
        except Exception as exc:  # noqa: BLE001 - state must surface the runtime failure
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"
                self._state = PaperControlState.FAILED

    def start(self) -> PaperControlSnapshot:
        with self._lock:
            if self._state in {
                PaperControlState.STARTING,
                PaperControlState.RUNNING,
                PaperControlState.PAUSED,
                PaperControlState.STOPPING,
            }:
                raise RuntimeError(f"paper session already active: {self._state.value}")
            self._runtime = self._runtime_factory()
            self._runtime.resume()
            self._kill_requested = False
            self._error = None
            self._state = PaperControlState.STARTING
            self._thread = Thread(target=self._run, name="stock-bot-paper", daemon=True)
            self._thread.start()
            self._state = PaperControlState.RUNNING
            return self.snapshot()

    def pause(self) -> PaperControlSnapshot:
        with self._lock:
            if self._runtime is None or self._state != PaperControlState.RUNNING:
                raise RuntimeError("paper session is not running")
            self._runtime.pause()
            self._state = PaperControlState.PAUSED
            return self.snapshot()

    def resume(self) -> PaperControlSnapshot:
        with self._lock:
            if self._runtime is None or self._state != PaperControlState.PAUSED:
                raise RuntimeError("paper session is not paused")
            self._runtime.resume()
            self._state = PaperControlState.RUNNING
            return self.snapshot()

    def stop(self) -> PaperControlSnapshot:
        with self._lock:
            if self._runtime is None:
                self._state = PaperControlState.STOPPED
                return self.snapshot()
            if self._state in {PaperControlState.STOPPED, PaperControlState.COMPLETED, PaperControlState.FAILED, PaperControlState.KILLED}:
                return self.snapshot()
            self._state = PaperControlState.STOPPING
            self._runtime.request_stop()
            return self.snapshot()

    def kill(self) -> PaperControlSnapshot:
        with self._lock:
            if self._runtime is None:
                self._state = PaperControlState.KILLED
                return self.snapshot()
            self._kill_requested = True
            self._state = PaperControlState.STOPPING
            self._runtime.request_kill()
            return self.snapshot()

    def snapshot(self) -> PaperControlSnapshot:
        with self._lock:
            runtime = self._runtime
            paper = runtime.paper_engine if runtime is not None else None
            result = runtime.paper_result if runtime is not None else None
            return PaperControlSnapshot(
                state=self._state.value,
                target_trades=paper.config.target_trades if paper is not None else self._target_trades,
                predictions=runtime.predictions if runtime is not None else 0,
                completed_trades=paper.completed_count if paper is not None else 0,
                net_pnl=float(result.metrics.net_pnl) if result is not None else None,
                error=self._error,
                broker_orders=0,
                trading_authority="NONE",
            )

    def dashboard(self) -> dict[str, Any]:
        """Return control state plus the runtime dashboard when initialized."""
        payload = {"paper_control": self.snapshot().__dict__ if False else None}
        snapshot = self.snapshot()
        payload["paper_control"] = {
            "state": snapshot.state,
            "target_trades": snapshot.target_trades,
            "predictions": snapshot.predictions,
            "completed_trades": snapshot.completed_trades,
            "net_pnl": snapshot.net_pnl,
            "error": snapshot.error,
            "broker_orders": 0,
            "trading_authority": "NONE",
        }
        if self._runtime is not None:
            payload["runtime"] = self._runtime.dashboard()
        return payload


__all__ = ["PaperControlPlane", "PaperControlSnapshot", "PaperControlState"]
