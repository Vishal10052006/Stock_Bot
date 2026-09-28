import json
from pathlib import Path


def test_ops_dashboard_assets_are_present_and_safe():
    """Dashboard assets must remain static, parseable, and explicitly locked."""
    root = Path(__file__).resolve().parents[2]
    html = (root / "dashboard" / "index.html").read_text(encoding="utf-8")
    snapshot = json.loads(
        (root / "dashboard" / "demo_snapshot.json").read_text(encoding="utf-8")
    )

    assert "STOCK_BOT / OPS_CENTER" in html
    assert "LIVE: LOCKED" in html
    assert "NO ORDER AUTHORITY" in html
    assert "MONITORINGRUNTIME.DASHBOARD()" in html

    assert snapshot["mode"] == "research_paper_demo"
    assert snapshot["metrics"]["execution.fill_count"] == 0
    assert snapshot["health"][4]["status"] == "LOCKED"
