from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np


class PipeWireCaptureError(RuntimeError):
    """Raised when PipeWire/GStreamer frame capture cannot be started."""


@dataclass(frozen=True, slots=True)
class ScreenFrame:
    """One decoded RGB desktop frame with causal capture metadata."""

    frame: np.ndarray
    observed_at: datetime
    width: int
    height: int
    format: str
    pts_ns: int | None
    duration_ns: int | None

    def __post_init__(self) -> None:
        if self.frame.dtype != np.uint8:
            raise ValueError("ScreenFrame.frame must have dtype uint8")
        if self.frame.ndim != 3 or self.frame.shape[2] != 3:
            raise ValueError(
                "ScreenFrame.frame must have shape (height, width, 3)"
            )
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ScreenFrame dimensions must be positive")
        if self.frame.shape[:2] != (self.height, self.width):
            raise ValueError(
                "ScreenFrame dimensions do not match frame shape"
            )
        if self.observed_at.tzinfo is None:
            raise ValueError("ScreenFrame.observed_at must be timezone-aware")


class PipeWireFrameCapture:
    """
    Decode one XDG ScreenCast PipeWire node through GStreamer.

    Pipeline:
        pipewiresrc -> videoconvert -> capsfilter(RGB) -> appsink

    This class is observation-only. It never creates trading actions.
    """

    def __init__(
        self,
        pipewire_fd: int,
        node_id: int,
        *,
        max_buffers: int = 2,
    ) -> None:
        if pipewire_fd < 0:
            raise ValueError("pipewire_fd must be non-negative")
        if node_id < 0:
            raise ValueError("node_id must be non-negative")
        if max_buffers < 1:
            raise ValueError("max_buffers must be at least 1")

        self.pipewire_fd = pipewire_fd
        self.node_id = node_id
        self.max_buffers = max_buffers

        self._gst: Any | None = None
        self._pipeline: Any | None = None
        self._appsink: Any | None = None
        self._owned_fd: int | None = None
        self._started = False
        self._latest_frame: ScreenFrame | None = None

    @property
    def latest_frame(self) -> ScreenFrame | None:
        return self._latest_frame

    @staticmethod
    def _load_gstreamer() -> tuple[Any, Any]:
        try:
            import gi

            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
        except (ImportError, ValueError) as exc:
            raise PipeWireCaptureError(
                "GStreamer Python bindings are unavailable. "
                "Install python3-gi and python3-gst-1.0."
            ) from exc

        Gst.init(None)

        if Gst.ElementFactory.find("pipewiresrc") is None:
            raise PipeWireCaptureError(
                "GStreamer pipewiresrc plugin is unavailable. "
                "Install the GStreamer PipeWire plugin."
            )

        if Gst.ElementFactory.find("appsink") is None:
            raise PipeWireCaptureError(
                "GStreamer appsink plugin is unavailable."
            )

        return Gst, gi

    @staticmethod
    def _set_if_property(element: Any, name: str, value: Any) -> bool:
        try:
            if element.find_property(name) is None:
                return False
            element.set_property(name, value)
            return True
        except Exception:
            return False

    def _build_pipeline(self) -> None:
        Gst, _gi = self._load_gstreamer()
        self._gst = Gst

        src = Gst.ElementFactory.make("pipewiresrc", "screen-source")
        convert = Gst.ElementFactory.make("videoconvert", "rgb-convert")
        capsfilter = Gst.ElementFactory.make("capsfilter", "rgb-caps")
        sink = Gst.ElementFactory.make("appsink", "frame-sink")

        if any(element is None for element in (src, convert, capsfilter, sink)):
            raise PipeWireCaptureError(
                "Failed to create the PipeWire/GStreamer capture elements"
            )

        self._owned_fd = os.dup(self.pipewire_fd)

        if not self._set_if_property(src, "fd", self._owned_fd):
            os.close(self._owned_fd)
            self._owned_fd = None
            raise PipeWireCaptureError(
                "pipewiresrc does not expose the required 'fd' property"
            )

        if not self._set_if_property(src, "target-object", str(self.node_id)):
            if not self._set_if_property(src, "target-object", self.node_id):
                raise PipeWireCaptureError(
                    "pipewiresrc does not expose a usable 'target-object' "
                    "property"
                )

        caps = Gst.Caps.from_string(
            "video/x-raw,format=RGB"
        )
        capsfilter.set_property("caps", caps)

        sink.set_property("max-buffers", self.max_buffers)
        sink.set_property("sync", False)
        sink.set_property("emit-signals", False)

        # GStreamer 1.28 uses leaky-type; older versions expose drop.
        if not self._set_if_property(sink, "leaky-type", 2):
            self._set_if_property(sink, "drop", True)

        pipeline = Gst.Pipeline.new("screen-capture")
        if pipeline is None:
            raise PipeWireCaptureError("Failed to create GStreamer pipeline")

        pipeline.add(src)
        pipeline.add(convert)
        pipeline.add(capsfilter)
        pipeline.add(sink)

        if not src.link(convert):
            raise PipeWireCaptureError("Failed to link pipewiresrc -> videoconvert")
        if not convert.link(capsfilter):
            raise PipeWireCaptureError("Failed to link videoconvert -> capsfilter")
        if not capsfilter.link(sink):
            raise PipeWireCaptureError("Failed to link capsfilter -> appsink")

        self._pipeline = pipeline
        self._appsink = sink

    def start(self) -> None:
        if self._started:
            return

        try:
            self._build_pipeline()
            assert self._pipeline is not None
            state = self._pipeline.set_state(self._gst.State.PLAYING)
            if state == self._gst.StateChangeReturn.FAILURE:
                raise PipeWireCaptureError(
                    "GStreamer pipeline failed to enter PLAYING"
                )
            self._started = True
        except Exception:
            self.stop()
            raise

    def read_frame(self, timeout_seconds: float = 2.0) -> ScreenFrame | None:
        if not self._started or self._appsink is None or self._gst is None:
            raise PipeWireCaptureError(
                "Capture must be started before read_frame()"
            )
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")

        timeout_ns = int(timeout_seconds * self._gst.SECOND)
        sample = self._appsink.emit("try-pull-sample", timeout_ns)
        if sample is None:
            return None

        caps = sample.get_caps()
        structure = caps.get_structure(0)
        width = int(structure.get_value("width"))
        height = int(structure.get_value("height"))
        fmt = str(structure.get_value("format"))

        if fmt != "RGB":
            raise PipeWireCaptureError(
                f"Expected RGB frame, received {fmt!r}"
            )

        buffer = sample.get_buffer()
        success, map_info = buffer.map(self._gst.MapFlags.READ)
        if not success:
            raise PipeWireCaptureError("Failed to map GStreamer frame buffer")

        try:
            expected_size = width * height * 3
            if map_info.size < expected_size:
                raise PipeWireCaptureError(
                    f"Frame buffer is too small: {map_info.size} < {expected_size}"
                )
            array = np.frombuffer(
                map_info.data,
                dtype=np.uint8,
                count=expected_size,
            ).reshape((height, width, 3)).copy()
        finally:
            buffer.unmap(map_info)

        pts = buffer.pts
        duration = buffer.duration
        pts_ns = None if pts == self._gst.CLOCK_TIME_NONE else int(pts)
        duration_ns = (
            None
            if duration == self._gst.CLOCK_TIME_NONE
            else int(duration)
        )

        frame = ScreenFrame(
            frame=array,
            observed_at=datetime.now(timezone.utc),
            width=width,
            height=height,
            format=fmt,
            pts_ns=pts_ns,
            duration_ns=duration_ns,
        )
        self._latest_frame = frame
        return frame

    def stop(self) -> None:
        if self._pipeline is not None and self._gst is not None:
            try:
                self._pipeline.set_state(self._gst.State.NULL)
            except Exception:
                pass

        self._pipeline = None
        self._appsink = None
        self._started = False
        self._latest_frame = None

        if self._owned_fd is not None:
            try:
                os.close(self._owned_fd)
            except OSError:
                pass
            self._owned_fd = None

    def __enter__(self) -> "PipeWireFrameCapture":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()
