from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from dashboard.paper_control import PaperControlPlane, PaperControlState


class FakeRuntime:
    def __init__(self) -> None:
        self.predictions = 0
        self.paper_result = None
        self.paused = False
        self.stopped = False
        self.killed = False
        self.paper_engine = SimpleNamespace(
            completed_count=0,
            session_completed=False,
            config=SimpleNamespace(target_trades=2),
        )

    def resume(self) -> None:
        self.paused = False

    def pause(self) -> None:
        self.paused = True

    def request_stop(self) -> None:
        self.stopped = True

    def request_kill(self) -> None:
        self.killed = True

    def run(self):
        self.predictions += 1
        while not self.stopped and not self.killed:
            time.sleep(0.01)
            break
        return ()

    def dashboard(self):
        return {"live_model": {"broker_orders": 0, "trading_authority": "NONE"}}


def test_control_plane_lifecycle_is_paper_only():
    runtime = FakeRuntime()
    control = PaperControlPlane(lambda: runtime, target_trades=2)

    assert control.snapshot().state == PaperControlState.STOPPED.value

    control.start()
    assert control.snapshot().state in {
        PaperControlState.RUNNING.value,
        PaperControlState.STOPPED.value,
    }

    if control.snapshot().state == PaperControlState.RUNNING.value:
        control.pause()
        assert control.snapshot().state == PaperControlState.PAUSED.value
        control.resume()
        assert control.snapshot().state == PaperControlState.RUNNING.value
        control.stop()

    for _ in range(50):
        if control.snapshot().state in {PaperControlState.STOPPED.value, PaperControlState.COMPLETED.value}:
            break
        time.sleep(0.01)

    snapshot = control.snapshot()
    assert snapshot.broker_orders == 0
    assert snapshot.trading_authority == "NONE"


def test_kill_switch_requests_emergency_stop():
    runtime = FakeRuntime()
    control = PaperControlPlane(lambda: runtime, target_trades=2)
    control.start()
    control.kill()
    assert runtime.killed is True


def test_invalid_target_trades_rejected():
    with pytest.raises(ValueError):
        PaperControlPlane(lambda: FakeRuntime(), target_trades=0)
