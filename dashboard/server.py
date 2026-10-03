"""Local V1 human-review dashboard server.

The server is intentionally local and broker-free. It:
- serves dashboard/index.html;
- exposes the latest operator snapshot read-only;
- records explicit ACCEPT/REJECT review decisions;
- records only operator-supplied manual outcomes.

It never submits, modifies, cancels, or infers broker orders.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from journal.manual_review import (
    ManualOutcomeRecord,
    ManualOutcomeStatus,
    ManualReviewAction,
    ManualReviewJournal,
    ManualReviewStore,
)
from v1_signal.contracts import V1SignalContract


class DashboardConfigurationError(RuntimeError):
    """Raised when a required dashboard runtime path is missing or invalid."""


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DashboardConfigurationError(f"snapshot file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DashboardConfigurationError(f"snapshot file is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise DashboardConfigurationError("operator snapshot must be a JSON object")
    return payload


def _signal_from_snapshot(snapshot: dict[str, Any]) -> V1SignalContract:
    payload = snapshot.get("v1_signal")
    if payload is None:
        payload = snapshot.get("views", {}).get("v1_signal")
    if not isinstance(payload, dict):
        raise DashboardConfigurationError("snapshot does not contain a canonical v1_signal object")
    return V1SignalContract.from_dict(payload)


def _outcome_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "OUT-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def _parse_optional_float(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    return None if value is None or value == "" else float(value)


def _parse_optional_datetime(payload: dict[str, Any], key: str) -> datetime | None:
    value = payload.get(key)
    return None if value in (None, "") else datetime.fromisoformat(str(value))


def build_journal(
    *,
    snapshot_path: Path,
    journal_path: Path,
) -> ManualReviewJournal:
    if not snapshot_path.is_absolute():
        snapshot_path = snapshot_path.resolve()
    if not journal_path.is_absolute():
        journal_path = journal_path.resolve()
    return ManualReviewJournal(ManualReviewStore(journal_path))


def record_review(
    *,
    snapshot_path: Path,
    journal: ManualReviewJournal,
    action: str,
    reviewed_at: datetime,
    review_note: str,
):
    signal = _signal_from_snapshot(_read_json(snapshot_path))
    review_action = ManualReviewAction(action)
    if review_action is ManualReviewAction.ACCEPT and signal.is_expired:
        raise ValueError("expired V1 signals cannot be accepted")
    return journal.record_review(
        signal,
        action=review_action,
        reviewed_at=reviewed_at,
        review_note=review_note,
    )


def record_outcome(
    *,
    journal: ManualReviewJournal,
    payload: dict[str, Any],
) -> ManualOutcomeRecord:
    review_id = str(payload.get("review_id", "")).strip()
    if not review_id:
        raise ValueError("review_id is required")

    reviews = {review.review_id: review for review in journal.reviews()}
    review = reviews.get(review_id)
    if review is None:
        raise ValueError("review_id does not exist")

    observed_at = datetime.fromisoformat(str(payload["observed_at"]))
    status = ManualOutcomeStatus(str(payload["status"]))
    outcome_payload = {
        "review_id": review_id,
        "signal_id": review.signal_id,
        "observed_at": observed_at.isoformat(),
        "status": status.value,
        "execution_timestamp": (
            _parse_optional_datetime(payload, "execution_timestamp").isoformat()
            if _parse_optional_datetime(payload, "execution_timestamp") is not None
            else None
        ),
        "entry_price": _parse_optional_float(payload, "entry_price"),
        "exit_timestamp": (
            _parse_optional_datetime(payload, "exit_timestamp").isoformat()
            if _parse_optional_datetime(payload, "exit_timestamp") is not None
            else None
        ),
        "exit_price": _parse_optional_float(payload, "exit_price"),
        "quantity": _parse_optional_float(payload, "quantity"),
        "fees": _parse_optional_float(payload, "fees"),
        "slippage_cost": _parse_optional_float(payload, "slippage_cost"),
        "net_pnl": _parse_optional_float(payload, "net_pnl"),
        "note": str(payload.get("note", "")),
    }
    outcome = ManualOutcomeRecord(
        outcome_id=_outcome_id(outcome_payload),
        review_id=review_id,
        signal_id=review.signal_id,
        observed_at=observed_at,
        status=status,
        execution_timestamp=_parse_optional_datetime(payload, "execution_timestamp"),
        entry_price=_parse_optional_float(payload, "entry_price"),
        exit_timestamp=_parse_optional_datetime(payload, "exit_timestamp"),
        exit_price=_parse_optional_float(payload, "exit_price"),
        quantity=_parse_optional_float(payload, "quantity"),
        fees=_parse_optional_float(payload, "fees"),
        slippage_cost=_parse_optional_float(payload, "slippage_cost"),
        net_pnl=_parse_optional_float(payload, "net_pnl"),
        note=str(payload.get("note", "")),
    )
    journal.record_outcome(outcome)
    return outcome


class DashboardHandler(BaseHTTPRequestHandler):
    snapshot_path: Path
    journal: ManualReviewJournal
    dashboard_path: Path

    def _send_json(self, status: int, payload: Any) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _request_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        try:
            if route == "/":
                self._send_file(self.dashboard_path)
                return
            if route == "/api/snapshot":
                self._send_json(200, _read_json(self.snapshot_path))
                return
            if route == "/api/reviews":
                self._send_json(
                    200,
                    {
                        "reviews": [item.to_dict() for item in self.journal.reviews()],
                        "outcomes": [item.to_dict() for item in self.journal.outcomes()],
                    },
                )
                return
            self._send_json(404, {"error": "not_found"})
        except DashboardConfigurationError as exc:
            self._send_json(503, {"error": str(exc)})
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        try:
            payload = self._request_json()
            if route == "/api/review":
                action = str(payload.get("action", "")).strip().upper()
                if action not in {item.value for item in ManualReviewAction}:
                    raise ValueError("action must be ACCEPT or REJECT")
                record = record_review(
                    snapshot_path=self.snapshot_path,
                    journal=self.journal,
                    action=action,
                    reviewed_at=datetime.fromisoformat(str(payload["reviewed_at"])),
                    review_note=str(payload.get("review_note", "")),
                )
                self._send_json(201, record.to_dict())
                return

            if route == "/api/outcome":
                record = record_outcome(journal=self.journal, payload=payload)
                self._send_json(201, record.to_dict())
                return

            self._send_json(404, {"error": "not_found"})
        except (DashboardConfigurationError, KeyError, TypeError, ValueError) as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[dashboard] {fmt % args}")


def serve(*, host: str, port: int, snapshot_path: Path, journal_path: Path) -> None:
    dashboard_path = Path(__file__).with_name("index.html")
    if not dashboard_path.exists():
        raise DashboardConfigurationError(f"dashboard index does not exist: {dashboard_path}")

    journal = build_journal(snapshot_path=snapshot_path, journal_path=journal_path)

    handler = type(
        "ConfiguredDashboardHandler",
        (DashboardHandler,),
        {
            "snapshot_path": snapshot_path,
            "journal": journal,
            "dashboard_path": dashboard_path,
        },
    )
    server = ThreadingHTTPServer((host, port), handler)
    print(f"STOCK_BOT V1 dashboard: http://{host}:{port}/")
    print(f"snapshot: {snapshot_path}")
    print(f"journal: {journal_path}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the local STOCK_BOT V1 manual-review dashboard.")
    parser.add_argument("--snapshot-path", required=True, type=Path)
    parser.add_argument("--journal-path", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    serve(
        host=args.host,
        port=args.port,
        snapshot_path=args.snapshot_path,
        journal_path=args.journal_path,
    )


if __name__ == "__main__":
    main()
