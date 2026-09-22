"""Consolidated Phase 9 contract smoke test.

Runs deterministic unit-level checks for P9-00 through P9-17 without
requiring broker credentials or a real-data download.

References:
    docs/PHASE_9_SPEC.md
    docs/PHASE_9_EXPERIMENT.md
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _compile_phase9_scripts() -> None:
    """Fail closed if the real-data runners contain syntax errors."""
    import py_compile

    for path in (
        ROOT / "scripts" / "build_phase9_real_dataset.py",
        ROOT / "scripts" / "run_phase9_experiment.py",
    ):
        py_compile.compile(str(path), doraise=True)

def main() -> int:
    """Run the Phase 9-focused test surface."""
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/models/test_logistic.py",
        "tests/models/test_random_forest.py",
        "tests/models/test_calibration.py",
        "tests/models/test_prediction_contract.py",
        "tests/evaluation/test_phase9_tools.py",
        "tests/strategy/test_baseline.py",
        "tests/test_strategy_prediction_adapter.py",
        "tests/labeling/test_labeling.py",
        "tests/features/test_feature_causality.py",
        "tests/features/test_feature_validation.py",
    ]

    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
