"""Local operator server for the STOCK_BOT paper dashboard.

Serves the static dashboard and a small same-origin JSON control API.
No endpoint can authorize or submit a broker order.
"""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from functools import partial

from dashboard.paper_control import PaperControlPlane
from ml.prediction.live_runtime import LiveModelRuntime, LiveModelRuntimeConfig


class DashboardHandler(SimpleHTTPRequestHandler):
    control: PaperControlPlane
    dashboard_root: Path

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _api(self) -> bool:
        return self.path.startswith("/api/")

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/control/status":
            self._json(HTTPStatus.OK, self.control.dashboard())
            return
        if self.path == "/api/dashboard":
            self._json(HTTPStatus.OK, self.control.dashboard())
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        routes = {
            "/api/control/start": self.control.start,
            "/api/control/pause": self.control.pause,
            "/api/control/resume": self.control.resume,
            "/api/control/stop": self.control.stop,
            "/api/control/kill": self.control.kill,
        }
        action = routes.get(self.path)
        if action is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "unknown control endpoint"})
            return
        try:
            snapshot = action()
            self._json(HTTPStatus.OK, {
                "paper_control": {
                    "state": snapshot.state,
                    "target_trades": snapshot.target_trades,
                    "predictions": snapshot.predictions,
                    "completed_trades": snapshot.completed_trades,
                    "net_pnl": snapshot.net_pnl,
                    "error": snapshot.error,
                    "broker_orders": 0,
                    "trading_authority": "NONE",
                }
            })
        except RuntimeError as exc:
            self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001 - HTTP boundary must return structured failure
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[dashboard] {format % args}")


def build_server(*, host: str, port: int, config: LiveModelRuntimeConfig) -> ThreadingHTTPServer:
    control = PaperControlPlane(
        lambda: LiveModelRuntime.from_env(config),
        target_trades=config.target_trades,
    )
    root = Path(__file__).resolve().parent
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"control": control})
    bound_handler = partial(handler, directory=str(root))
    return ThreadingHTTPServer((host, port), bound_handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="STOCK_BOT paper dashboard operator server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--symbol", default="RELIANCE")
    parser.add_argument("--target-trades", type=int, default=10)
    parser.add_argument("--max-predictions", type=int, default=500)
    args = parser.parse_args()

    config = LiveModelRuntimeConfig(
        symbol=args.symbol,
        target_trades=args.target_trades,
        max_predictions=args.max_predictions,
    )
    server = build_server(host=args.host, port=args.port, config=config)
    print(f"STOCK_BOT dashboard: http://{args.host}:{args.port}/index.html")
    print("Paper control API: /api/control/{start,pause,resume,stop,kill}")
    print("LIVE BROKER AUTHORITY: NONE")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
