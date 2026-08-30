"""Pytest configuration for the repository test suite.

The project is currently a source-tree application rather than an installed
Python package. Adding the repository root to ``sys.path`` lets both existing
``core`` imports and the new Phase 3 ``market`` package resolve consistently.
"""

from pathlib import Path
import sys


# Keep tests runnable directly from the repository checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
