"""Print the current fail-closed STOCK_BOT live-readiness state."""

from __future__ import annotations

from trading.runtime_cli import run_readiness


if __name__ == "__main__":
    raise SystemExit(run_readiness())
