#!/usr/bin/env python3
"""CLI for validating Screen Observer against a real screenshot.

Usage:
    python scripts/validate_screen_observer.py /path/to/tradingview.png
    python scripts/validate_screen_observer.py /path/to/tradingview.png --pretty
"""

from __future__ import annotations

import argparse
import json
import sys

from screen_observer.validation import validate_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate S04-S08 Screen Observer vision on one screenshot."
    )
    parser.add_argument("image", help="Path to PNG/JPEG/WebP screenshot.")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON report.",
    )
    args = parser.parse_args()

    try:
        report = validate_file(args.image)
    except Exception as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1

    if args.pretty:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(report, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
