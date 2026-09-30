#!/usr/bin/env python3
"""Automatically monitor the STOCK_BOT live paper session.

This is a read-only operator utility. It polls the local dashboard status API,
prints progress, and exits when the paper session reaches a terminal state or
the configured trade target is reached.

It never starts, stops, pauses, kills, or submits broker orders.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TERMINAL_STATES = {"COMPLETED", "FAILED", "STOPPED", "KILLED"}


def fetch_status(url: str, timeout: float) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)

    if not isinstance(payload, dict):
        raise ValueError("dashboard returned a non-object JSON payload")
    return payload


def _value(data: dict, *path: str, default=None):
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def print_status(payload: dict, *, previous: tuple | None = None) -> tuple:
    paper = payload.get("paper_control") or {}
    runtime = payload.get("runtime") or {}
    live_model = runtime.get("live_model") or {}
    health = runtime.get("health") or {}

    state = paper.get("state", "UNKNOWN")
    predictions = paper.get("predictions", 0)
    completed = paper.get("completed_trades", 0)
    target = paper.get("target_trades", 0)
    pnl = paper.get("net_pnl")
    error = paper.get("error")
    authority = paper.get("trading_authority", "UNKNOWN")
    broker_orders = paper.get("broker_orders", "UNKNOWN")
    lifecycle = _value(runtime, "live_runtime", "lifecycle_state", default="-")
    predicted_class = live_model.get("predicted_class", "-")
    timestamp = live_model.get("timestamp") or runtime.get("timestamp") or "-"

    analysis = health.get("analysis_bot") or {}
    analysis_status = analysis.get("status", "-")
    completeness = analysis.get("completeness")

    key = (
        state,
        predictions,
        completed,
        target,
        pnl,
        error,
        timestamp,
        predicted_class,
        lifecycle,
        analysis_status,
        completeness,
    )
    if key == previous:
        return key

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    progress = f"{completed}/{target}" if target else str(completed)
    pnl_text = "n/a" if pnl is None else f"{float(pnl):.4f}"
    completeness_text = (
        "n/a" if completeness is None else f"{float(completeness) * 100:.1f}%"
    )

    print(
        f"[{now}] "
        f"state={state} | predictions={predictions} | trades={progress} | "
        f"pnl={pnl_text} | class={predicted_class} | "
        f"analysis={analysis_status} ({completeness_text}) | "
        f"lifecycle={lifecycle}"
    )
    print(
        f"           model_ts={timestamp} | "
        f"broker_orders={broker_orders} | authority={authority}"
    )
    if error:
        print(f"           ERROR: {error}")

    return key


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only automatic monitor for the STOCK_BOT paper session"
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8765/api/control/status",
        help="paper dashboard status endpoint",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="seconds between status checks (default: 30)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="check once and exit",
    )
    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval must be positive")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    print("============================================================")
    print("STOCK_BOT — LIVE PAPER MONITOR")
    print("============================================================")
    print(f"Endpoint : {args.url}")
    print(f"Interval : {args.interval:g}s")
    print("Mode     : READ-ONLY (no control actions, no broker orders)")
    print("Press Ctrl+C to stop monitoring.")
    print()

    previous = None

    while True:
        try:
            payload = fetch_status(args.url, args.timeout)
            previous = print_status(payload, previous=previous)

            paper = payload.get("paper_control") or {}
            state = paper.get("state")
            completed = int(paper.get("completed_trades") or 0)
            target = int(paper.get("target_trades") or 0)

            if state in TERMINAL_STATES:
                print()
                print(f"MONITOR COMPLETE: paper session state={state}")
                if state == "COMPLETED" and target:
                    print(f"Target trades reached: {completed}/{target}")
                return 0 if state != "FAILED" else 1

            if target > 0 and completed >= target:
                print()
                print(f"MONITOR COMPLETE: target reached ({completed}/{target})")
                return 0

            if args.once:
                return 0

        except HTTPError as exc:
            print(f"[monitor] HTTP error {exc.code}: {exc.reason}", file=sys.stderr)
        except (URLError, TimeoutError, OSError) as exc:
            print(f"[monitor] connection error: {exc}", file=sys.stderr)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"[monitor] invalid dashboard response: {exc}", file=sys.stderr)

        if args.once:
            return 1

        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitor stopped by user.")
            return 130


if __name__ == "__main__":
    raise SystemExit(main())
