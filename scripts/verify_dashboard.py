#!/usr/bin/env python3
"""Deterministic dashboard completion verification.

This verifier checks the dashboard package, read-only safety invariants and its
local HTTP API. It does not claim broker readiness or production deployment.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/dashboard", "-p", "test_*.py", "-v"],
        cwd=ROOT,
        check=False,
    )
    if tests.returncode:
        return tests.returncode

    from dashboard.contracts import DashboardConfig
    from dashboard.server import DashboardServer
    from dashboard.service import DashboardService
    import threading
    import time

    with tempfile.TemporaryDirectory() as tmp:
        cfg = DashboardConfig(host="127.0.0.1", port=18766, journal_path=str(Path(tmp) / "events.jsonl"))
        service = DashboardService.from_environment(cfg)
        overview = service.overview()
        assert overview["live_trading"] == "LOCKED"
        assert overview["paper_only"] is True
        assert overview["causality"] == "ENFORCED"
        assert len(overview["agents"]) == 7

        server = DashboardServer(cfg, service=service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            time.sleep(0.05)
            with urlopen("http://127.0.0.1:18766/api/overview", timeout=2) as response:
                body = json.loads(response.read())
            assert body["summary"]["registered_agents"] == 7
        finally:
            server.shutdown()
            server.server_close()

    print("DASHBOARD PHASE 0-20 VERIFICATION: PASS")
    print("LIVE BROKER AUTHORITY: LOCKED")
    print("DASHBOARD AUTHORITY: OBSERVATION ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
