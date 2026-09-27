from __future__ import annotations

import pytest

from execution.engine import PositionSnapshot
from execution.adapters.upstox_position_evidence import run_upstox_position_evidence


def test_upstox_position_evidence_runner_reconciles_read_only_positions(monkeypatch):
    from execution.adapters import upstox_production_positions

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self):
            return (
                b'{"status":"success","data":[{"trading_symbol":"ITC",'
                b'"quantity":10,"average_price":450.0}]}'
            )

    seen = {}

    def fake_urlopen(request, timeout):
        seen["method"] = request.method
        seen["url"] = request.full_url
        return Response()

    monkeypatch.setattr(upstox_production_positions, "urlopen", fake_urlopen)

    result = run_upstox_position_evidence(
        "runtime-token",
        (PositionSnapshot("ITC", 10, 450.0),),
    )

    assert seen["method"] == "GET"
    assert seen["url"] == upstox_production_positions.PRODUCTION_POSITIONS_URL
    assert result.evidence.status == "MATCH"
    assert result.evidence.observed
    assert result.evidence.safe
    assert result.positions == (PositionSnapshot("ITC", 10, 450.0),)


def test_upstox_position_evidence_runner_preserves_mismatch(monkeypatch):
    from execution.adapters import upstox_production_positions

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self):
            return (
                b'{"status":"success","data":[{"trading_symbol":"ITC",'
                b'"quantity":9,"average_price":450.0}]}'
            )

    monkeypatch.setattr(
        upstox_production_positions,
        "urlopen",
        lambda request, timeout: Response(),
    )

    result = run_upstox_position_evidence(
        "runtime-token",
        (PositionSnapshot("ITC", 10, 450.0),),
    )

    assert result.evidence.status == "MISMATCH"
    assert not result.safe


def test_upstox_position_evidence_runner_never_logs_token(monkeypatch, capsys):
    from execution.adapters import upstox_production_positions

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self):
            return b'{"status":"success","data":[]}'

    monkeypatch.setattr(
        upstox_production_positions,
        "urlopen",
        lambda request, timeout: Response(),
    )

    token = "SECRET-TOKEN-DO-NOT-LOG"
    result = run_upstox_position_evidence(token, ())

    captured = capsys.readouterr()
    assert token not in captured.out
    assert token not in captured.err
    assert result.evidence.status == "MATCH"
