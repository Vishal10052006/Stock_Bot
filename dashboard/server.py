from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .contracts import DashboardConfig
from .service import DashboardService


class _Handler(BaseHTTPRequestHandler):
    server_version = "StockBotDashboard/1.1"

    def _json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, separators=(",", ":"), default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _static(self, name: str, content_type: str) -> None:
        root = Path(__file__).with_name("static").resolve()
        path = (root / name).resolve()
        if root not in path.parents:
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            raw = path.read_bytes()
        except OSError:
            return self.send_error(HTTPStatus.NOT_FOUND)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 256_000:
                return {}
            body = self.rfile.read(length)
            value = json.loads(body.decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except (ValueError, TypeError, json.JSONDecodeError):
            return {}

    @property
    def service(self) -> DashboardService:
        return self.server.dashboard_service

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path

        static = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
        }
        if path in static:
            return self._static(*static[path])

        if path == "/api/overview":
            return self._json(self.service.overview())
        if path == "/api/agents":
            return self._json(self.service.agents())
        if path == "/api/pipeline":
            return self._json(self.service.pipeline())
        if path == "/api/models":
            return self._json(self.service.models())
        if path == "/api/health":
            return self._json(self.service.health())
        if path == "/api/learning":
            return self._json(self.service.learning())
        if path == "/api/decisions":
            return self._json(
                self.service.decisions(query.get("correlation_id", [None])[0])
            )
        if path == "/api/events":
            return self._json(
                self.service.events(
                    int(query.get("limit", ["100"])[0]),
                    query.get("source", [None])[0],
                    query.get("event_type", [None])[0],
                    query.get("correlation_id", [None])[0],
                )
            )
        if path == "/api/replay":
            correlation_id = query.get("correlation_id", [None])[0]
            return self._json(
                self.service.replay(correlation_id),
                HTTPStatus.BAD_REQUEST if not correlation_id else HTTPStatus.OK,
            )
        if path == "/api/stream":
            return self._stream()

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            return self.send_error(HTTPStatus.NOT_FOUND)

        payload = self._read_json()
        message = str(payload.get("message", "")).strip()
        history = payload.get("history", [])
        if not message:
            return self._json({"error": "message is required"}, HTTPStatus.BAD_REQUEST)

        if not isinstance(history, list):
            history = []

        try:
            result = self.service.chat(message, history[-12:])
            return self._json(result)
        except Exception as exc:
            return self._json(
                {"error": f"AI command failed: {type(exc).__name__}: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _stream(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last = None
        try:
            for _ in range(120):
                xs = self.service.events(1)
                current = xs[-1]["event_id"] if xs else None
                if current and current != last:
                    last = current
                    payload = json.dumps(xs[-1], separators=(",", ":"))
                    self.wfile.write(f"event: telemetry\ndata: {payload}\n\n".encode())
                else:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
                time.sleep(self.service.config.refresh_seconds)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *_args: Any) -> None:
        pass


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, config: DashboardConfig, service: DashboardService | None = None):
        self.dashboard_service = service or DashboardService.from_environment(config)
        super().__init__((config.host, config.port), _Handler)


def serve(config: DashboardConfig | None = None) -> None:
    config = config or DashboardConfig()
    server = DashboardServer(config)
    print(f"STOCK_BOT OPS CENTER: http://{config.host}:{config.port}")
    server.serve_forever()
