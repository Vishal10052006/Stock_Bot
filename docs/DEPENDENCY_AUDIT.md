# STOCK BOT — Dependency & Environment Audit

## Current Environment

- Python: 3.14.4
- Interpreter: `/usr/bin/python3` (system), project environment uses `.venv/bin/python`
- pip: 25.1.1
- Virtual environment: `.venv`
- Test runner: pytest 9.1.1

## Current Project Dependency State

The repository currently has no `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `setup.py`, or `setup.cfg`.

The application source currently relies almost entirely on Python's standard library and internal modules. No market-data, numerical, machine-learning, backtesting, or broker SDK dependency has been introduced yet.

## Baseline Test Result

The initial pytest run fails during test collection with three existing code errors:

1. `tests/test_decision.py` and `tests/test_learning.py` instantiate `CEO` and call `simulate_decision()`, which fails because `CEO` has no `decision_simulator` attribute.
2. `tests/test_planner.py` calls `CEO.add_goal()`, which fails because `CEO` has no `goal_manager` attribute.

These failures are part of the Phase 0 baseline and should not be hidden by installing unrelated packages or changing tests before the underlying implementation is audited.

## Current Import/Code Findings

The import scan identified suspicious or broken imports that require later cleanup:

- `from unittest import result` in `core/decision_engine.py`
- `from unittest import loader` in `execution/execution_engine.py`
- `from core.reliability_manager import calculate_worker_reliability` in `intelligence/confidence_calculator.py`
- `from core.execution_trace import ExecutionTrace` in `utils/trace_logger.py`

These should be resolved as part of the code-quality cleanup phase, not patched blindly during dependency installation.

## Dependency Policy

Stock Bot will use a minimal, explicitly versioned dependency set. Packages will only be added when a phase actually requires them.

Expected future categories include:

- Data: NumPy, pandas
- Market data: provider-specific client(s)
- Indicators: either a small internal implementation or a validated technical-analysis library
- ML: scikit-learn and, only if justified later, gradient-boosting or deep-learning libraries
- Backtesting: preferably an internal event-driven engine to retain control over fills/costs
- Testing: pytest
- Quality: ruff/formatting/type-checking tools as the project stabilizes
- Broker: provider-specific SDK/API only at the execution phase

No trading/ML package should be installed until its phase requires it.

## Python Version Decision

Python 3.14.4 is currently installed and works for the existing code and virtual environment. The final Stock Bot Python baseline will be selected after compatibility checks for the planned scientific/ML/broker stack. Until then, the current `.venv` is retained and no downgrade is performed.

## Next Audit Step

1. Review the existing source imports and test failures.
2. Decide the supported Python baseline for the first data/ML phase.
3. Create a reproducible project dependency file.
4. Re-run the test suite and record the baseline.
5. Only then introduce the first market/data dependency.
