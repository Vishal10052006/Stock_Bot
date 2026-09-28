"""Preflight checks for the optional TimesFM experiment.

This script intentionally does not download model weights. It checks the local
Python/runtime environment and reports whether the optional dependency is
available. Loading a foundation model remains an explicit user action.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-free-disk-gb", type=float, default=2.0)
    args = parser.parse_args()

    print("=" * 72)
    print("FOUNDATION MODEL — PRE-FLIGHT CHECK")
    print("=" * 72)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Python >= 3.10: {sys.version_info >= (3, 10)}")

    timesfm_available = importlib.util.find_spec("timesfm") is not None
    torch_available = importlib.util.find_spec("torch") is not None
    print(f"TimesFM installed: {timesfm_available}")
    print(f"PyTorch installed: {torch_available}")

    free_bytes = shutil.disk_usage(os.getcwd()).free
    free_gb = free_bytes / (1024**3)
    print(f"Free disk (GB): {free_gb:.2f}")
    print(f"Free disk >= {args.min_free_disk_gb:.1f} GB: {free_gb >= args.min_free_disk_gb}")

    if sys.version_info < (3, 10):
        return 1
    if free_gb < args.min_free_disk_gb:
        return 1

    print()
    if timesfm_available and torch_available:
        print("STATUS: READY FOR EXPLICIT TIMESFM EXPERIMENT")
    else:
        print("STATUS: OPTIONAL DEPENDENCY NOT READY")
        print("Install only after reviewing the experiment/license gate:")
        print("  pip install 'timesfm[torch]'")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
