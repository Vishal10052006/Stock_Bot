import json
from pathlib import Path


def test_v1_dashboard_is_static_read_only_and_canonical():
    """The dashboard must present the V1 contract without order authority."""
    root = Path(__file__).resolve().parents[2]
    html = (root / "dashboard" / "index.html").read_text(encoding="utf-8")

    assert "STOCK_BOT" in html
    assert "VERSION 1 / HUMAN REVIEW" in html
    assert "BROKER EXECUTION: DISABLED" in html
    assert "CANONICAL SIGNAL" in html
    assert "Prediction evidence" in html
    assert "News / Research" in html
    assert "Technical" in html
    assert "Fundamental" in html
    assert "Market / Sector" in html
    assert 'fetch("/api/snapshot"' in html
    assert "order" not in html.lower() or "no order" in html.lower()


def test_demo_snapshot_remains_observation_only():
    """The legacy demo payload must not claim broker authority."""
    root = Path(__file__).resolve().parents[2]
    snapshot = json.loads(
        (root / "dashboard" / "demo_snapshot.json").read_text(encoding="utf-8")
    )

    assert snapshot["mode"] == "research_paper_demo"
    assert snapshot["metrics"]["execution.fill_count"] == 0
    assert snapshot["health"][4]["status"] == "LOCKED"
