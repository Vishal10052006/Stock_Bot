from datetime import timedelta
import pandas as pd
import pytest

from screen_observer.capture import CaptureSchedule, CaptureScheduler


def test_scheduler_is_due_without_previous_capture():
    scheduler = CaptureScheduler(CaptureSchedule(timedelta(seconds=5)))
    assert scheduler.due(
        now=pd.Timestamp("2026-10-02T09:30:00+05:30"),
        last_capture=None,
    )


def test_scheduler_respects_interval():
    scheduler = CaptureScheduler(CaptureSchedule(timedelta(seconds=5)))
    now = pd.Timestamp("2026-10-02T09:30:05+05:30")
    last = pd.Timestamp("2026-10-02T09:30:01+05:30")
    assert not scheduler.due(now=now, last_capture=last)

    last = pd.Timestamp("2026-10-02T09:30:00+05:30")
    assert scheduler.due(now=now, last_capture=last)


def test_scheduler_rejects_naive_time():
    scheduler = CaptureScheduler(CaptureSchedule(timedelta(seconds=5)))
    with pytest.raises(ValueError):
        scheduler.due(now=pd.Timestamp("2026-10-02 09:30"), last_capture=None)
