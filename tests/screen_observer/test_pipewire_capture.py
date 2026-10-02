from datetime import datetime, timezone

import numpy as np
import pytest

from screen_observer.pipewire_capture import (
    PipeWireFrameCapture,
    ScreenFrame,
)


def test_screen_frame_contract():
    observed_at = datetime.now(timezone.utc)
    frame = np.zeros((4, 6, 3), dtype=np.uint8)

    result = ScreenFrame(
        frame=frame,
        observed_at=observed_at,
        width=6,
        height=4,
        format="RGB",
        pts_ns=123,
        duration_ns=40_000_000,
    )

    assert result.frame.shape == (4, 6, 3)
    assert result.frame.dtype == np.uint8
    assert result.width == 6
    assert result.height == 4
    assert result.format == "RGB"
    assert result.pts_ns == 123


def test_screen_frame_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        ScreenFrame(
            frame=np.zeros((2, 2, 3), dtype=np.uint8),
            observed_at=datetime.now(),
            width=2,
            height=2,
            format="RGB",
            pts_ns=None,
            duration_ns=None,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pipewire_fd": -1, "node_id": 1},
        {"pipewire_fd": 1, "node_id": -1},
        {"pipewire_fd": 1, "node_id": 1, "max_buffers": 0},
    ],
)
def test_capture_validates_configuration(kwargs):
    with pytest.raises(ValueError):
        PipeWireFrameCapture(**kwargs)


def test_capture_requires_start_before_reading():
    capture = PipeWireFrameCapture(3, 86)

    with pytest.raises(RuntimeError, match="started"):
        capture.read_frame()
