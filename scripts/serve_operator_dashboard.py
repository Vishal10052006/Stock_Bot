"""Serve the STOCK_BOT read-only operator dashboard from localhost.

The server exposes dashboard assets and a read-only /api/snapshot endpoint
backed by the supplied JSON snapshot file. It never accepts trading commands.
"""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse


def load_snapshot(path: Path) -> dict:
    """Load and structurally validate one operator snapshot."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("snapshot must be a JSON object")
    views = data.get("views", {})
    if not isinstance(views, dict):
        raise ValueError("snapshot.views must be an object")
    scanner = views.get("scanner")
    if scanner is not None and not isinstance(scanner, dict):
        raise ValueError("snapshot.views.scanner must be an object")
    return data


def make_handler(snapshot_path: Path, dashboard_dir: Path, review_snapshot_path: Path | None = None):
    """Create a request handler bound to immutable paths."""
    dashboard_root = Path(dashboard_dir).resolve()
    snapshot_file = Path(snapshot_path).resolve()
    review_file = Path(review_snapshot_path).resolve() if review_snapshot_path else None

    class OperatorHandler(SimpleHTTPRequestHandler):
        """Serve dashboard assets and the observation-only snapshot API."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(dashboard_root), **kwargs)

        def do_GET(self):  # noqa: N802
            request_path = urlparse(self.path).path
            if request_path == "/api/snapshot":
                try:
                    payload = load_snapshot(snapshot_file)
                except FileNotFoundError:
                    self.send_error(404, "snapshot not available yet")
                    return
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    self.send_error(500, f"invalid snapshot: {exc}")
                    return

                if review_file is not None and review_file.exists():
                    try:
                        review = json.loads(review_file.read_text(encoding="utf-8"))
                        if isinstance(review, dict):
                            payload["screen_review"] = review
                    except (OSError, ValueError, json.JSONDecodeError):
                        payload["screen_review"] = {
                            "status": "UNAVAILABLE",
                            "severity": "WARNING",
                            "authority": "OBSERVATION_ONLY",
                        }

                body = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            super().do_GET()

        def log_message(self, fmt, *args):
            """Keep the server log compact."""
            print(f"[dashboard] {self.address_string()} - {fmt % args}")

    return OperatorHandler


def build_parser() -> argparse.ArgumentParser:
    """Build the local dashboard server CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--dashboard-dir", type=Path, default=Path("dashboard"))
    parser.add_argument("--review-snapshot", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the read-only dashboard server."""
    args = build_parser().parse_args(argv)
    dashboard_dir = args.dashboard_dir.resolve()
    snapshot_path = args.snapshot.resolve()

    if not dashboard_dir.is_dir():
        raise FileNotFoundError(f"dashboard directory does not exist: {dashboard_dir}")
    if not 1 <= args.port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("operator dashboard must bind to localhost")

    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(snapshot_path, dashboard_dir, args.review_snapshot),
    )
    print(f"STOCK_BOT dashboard: http://{args.host}:{args.port}/")
    print(f"Snapshot source: {snapshot_path}")
    print("Authority: OBSERVATION_ONLY | LIVE BROKER: LOCKED")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
