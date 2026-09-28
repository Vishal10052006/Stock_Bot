"""STOCK_BOT boot entrypoint.

M20 changes the default root runtime to the fail-closed real-market SHADOW
runtime. It consumes Upstox market data and never submits broker orders.
"""

from scripts.run_m20_shadow import main


if __name__ == "__main__":
    raise SystemExit(main())
