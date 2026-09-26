"""M20.7 operator dashboard composition.

This module aggregates existing observational telemetry. It never authorizes
trades, changes risk, or exposes a broker-order submission path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .jarvis import JarvisLifecycle
from .shadow_runtime import ShadowRuntime


@dataclass(slots=True)
class JarvisDashboard:
    lifecycle: JarvisLifecycle
    shadow_runtime: ShadowRuntime | None = None

    def snapshot(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "system": {
                "mode": self.lifecycle.safety.mode,
                "live_broker_order_submission": False,
            },
            "lifecycle": self.lifecycle.dashboard(),
            "feed": None,
            "market_data": None,
            "decisions": None,
            "risk": None,
            "paper_execution": None,
            "research": None,
            "learning": None,
            "safety": {
                "mode": self.lifecycle.safety.mode,
                "live_broker_order_submission": False,
                "fail_closed": True,
            },
        }

        if self.shadow_runtime is not None:
            evidence = self.shadow_runtime.evidence()
            payload["feed"] = evidence.get("feed")
            payload["market_data"] = {
                "health": evidence.get("health"),
                "candle_buffer_symbols": evidence.get("shadow_candle_buffer_symbols", []),
                "candle_buffer_counts": evidence.get("shadow_candle_buffer_counts", {}),
            }
            payload["paper_execution"] = {
                "enabled": False,
                "live_broker_order_submission": False,
            }
            payload["monitoring"] = evidence.get("monitoring_dashboard")
            payload["session_journal"] = evidence.get("session_journal")
            payload["session_manifest"] = evidence.get("session_manifest")

        return payload

    def render_html(self) -> str:
        """Render a dependency-free operator dashboard."""
        snapshot = self.snapshot()
        import html
        import json

        data = html.escape(json.dumps(snapshot, indent=2, sort_keys=True, default=str))
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>STOCK_BOT JARVIS Dashboard</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;background:#101418;color:#e8eef2}}
pre{{white-space:pre-wrap;background:#171d22;padding:1rem;border-radius:8px}}
.badge{{display:inline-block;padding:.35rem .6rem;border-radius:999px;background:#24313a}}
</style>
</head>
<body>
<h1>STOCK_BOT — JARVIS</h1>
<p class="badge">MODE: {html.escape(str(snapshot["system"]["mode"]))}</p>
<p>LIVE BROKER ORDER SUBMISSION: <strong>DISABLED</strong></p>
<pre>{data}</pre>
</body>
</html>"""
