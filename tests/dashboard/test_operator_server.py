from __future__ import annotations

import json

from scripts.serve_operator_dashboard import load_snapshot


def test_operator_server_loads_valid_snapshot(tmp_path):
    """Dashboard server accepts a valid observation snapshot."""
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"views": {"scanner": {"status": "READY"}}}), encoding="utf-8")
    assert load_snapshot(path)["views"]["scanner"]["status"] == "READY"
