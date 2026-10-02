#!/usr/bin/env python3
"""List Linux desktop windows visible to Screen Observer S02."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from screen_observer import LinuxWindowProvider


def main() -> int:
    windows = LinuxWindowProvider()()

    if not windows:
        print("No windows detected.")
        print("Check that 'wmctrl' is installed and that the desktop session exposes X11 window metadata.")
        return 0

    for index, window in enumerate(windows, start=1):
        print(
            f"{index:02d} | {window.application:<24} | "
            f"{window.width}x{window.height}+{window.left}+{window.top} | "
            f"{window.title}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
