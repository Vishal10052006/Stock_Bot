"""Print the current live prediction correctness report.

This script reads the append-only live-validation journal produced by the
shadow validation runtime. It never submits orders and never changes model
state.
"""

from __future__ import annotations

import argparse

from live_validation import LivePredictionEvaluator, LiveValidationJournal


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate resolved live prediction outcomes."
    )
    parser.add_argument(
        "--journal",
        default="data/live_validation/predictions.jsonl",
        help="Path to the live-validation JSONL journal.",
    )
    args = parser.parse_args()

    journal = LiveValidationJournal(args.journal)
    LivePredictionEvaluator(journal).print_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
