"""Run one or more safe JARVIS lifecycle phases.

This command is control-plane only. It does not create a broker execution path.
"""

from __future__ import annotations

import argparse
import json

from runtime.jarvis import JarvisLifecycle, LifecyclePhase
from runtime.jarvis_dashboard import JarvisDashboard
from runtime.mode import load_runtime_safety


def main() -> int:
    parser = argparse.ArgumentParser(description="STOCK_BOT JARVIS lifecycle")
    parser.add_argument("--phase", choices=[item.value for item in LifecyclePhase])
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()

    lifecycle = JarvisLifecycle(safety=load_runtime_safety())
    if args.phase:
        lifecycle.run_phase(LifecyclePhase(args.phase))
    else:
        lifecycle.run_daily()

    dashboard = JarvisDashboard(lifecycle)
    if args.dashboard:
        print(dashboard.render_html())
    else:
        print(json.dumps(dashboard.snapshot(), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
