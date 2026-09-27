"""STOCK_BOT application entry point."""

from __future__ import annotations

from trading.runtime_cli import main as runtime_main


if __name__ == "__main__":
    raise SystemExit(runtime_main())
