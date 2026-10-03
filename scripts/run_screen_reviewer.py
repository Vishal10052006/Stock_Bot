"""Run the continuous observation-only desktop reviewer.

Example:
    python scripts/run_screen_reviewer.py \
      --snapshot paper/virtual_sessions/PAPER-YYYYMMDD/operator_snapshot.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from monitoring.screen_reviewer_runtime import ScreenReviewerRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--max-age", type=float, default=30.0)
    parser.add_argument("--min-confidence", type=float, default=0.70)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output or args.snapshot.with_name("screen_review.json")
    runtime = ScreenReviewerRuntime(
        operator_snapshot_path=args.snapshot,
        review_output_path=output,
        interval_seconds=args.interval,
        max_age_seconds=args.max_age,
        min_confidence=args.min_confidence,
    )
    print("STOCK_BOT SCREEN REVIEWER")
    print("Authority: OBSERVATION_ONLY")
    print(f"Operator snapshot: {args.snapshot}")
    print(f"Review output: {output}")
    print("Strategy/Risk/Safety/Execution authority: unchanged")
    runtime.start()
    try:
        while True:
            input()
    except (KeyboardInterrupt, EOFError):
        return 0
    finally:
        runtime.stop()


if __name__ == "__main__":
    raise SystemExit(main())
