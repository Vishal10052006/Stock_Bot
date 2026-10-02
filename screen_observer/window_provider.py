"""Linux desktop window enumeration adapter for Screen Observer S02.

The core observer consumes WindowObservation contracts only. This module keeps
Linux/window-manager details at the edge of the system.

Primary adapter:
    wmctrl -lGx

If wmctrl is unavailable or the command fails, the provider returns an empty
tuple rather than taking down the continuous observer.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Sequence

from .contracts import WindowObservation


class LinuxWindowProvider:
    """Enumerate desktop windows using the Linux wmctrl utility."""

    command = ("wmctrl", "-lGx")

    def __init__(self, *, timeout_seconds: float = 2.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    def __call__(self) -> tuple[WindowObservation, ...]:
        return self.list_windows()

    def list_windows(self) -> tuple[WindowObservation, ...]:
        """Return usable windows, or an empty tuple if enumeration is unavailable."""
        if shutil.which(self.command[0]) is None:
            return ()

        try:
            result = subprocess.run(
                self.command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError):
            return ()

        return self._parse_output(result.stdout)

    @staticmethod
    def _parse_output(output: str) -> tuple[WindowObservation, ...]:
        windows: list[WindowObservation] = []

        for line in output.splitlines():
            parts = line.split(maxsplit=8)
            if len(parts) < 9:
                continue

            try:
                _window_id, _desktop, left, top, width, height, wm_class, _host, title = parts
                left_i = int(left)
                top_i = int(top)
                width_i = int(width)
                height_i = int(height)
            except (TypeError, ValueError):
                continue

            if width_i <= 0 or height_i <= 0 or not title.strip():
                continue

            application = wm_class.strip()
            if "." in application:
                # wmctrl reports WM_CLASS as instance.class.
                application = application.rsplit(".", 1)[-1]

            windows.append(
                WindowObservation(
                    title=title.strip(),
                    application=application.strip() or "unknown",
                    left=left_i,
                    top=top_i,
                    width=width_i,
                    height=height_i,
                )
            )

        return tuple(windows)
