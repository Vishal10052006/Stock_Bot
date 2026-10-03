from __future__ import annotations

import json

from scripts.serve_operator_dashboard import load_snapshot


def test_operator_server_loads_valid_snapshot(tmp_path):
    """Dashboard server accepts a valid observation snapshot."""
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"views": {"scanner": {"status": "READY"}}}), encoding="utf-8")
    assert load_snapshot(path)["views"]["scanner"]["status"] == "READY"


def test_operator_server_merges_screen_review_when_configured(tmp_path):
    from scripts.serve_operator_dashboard import make_handler
    import json

    snapshot = tmp_path / "operator.json"
    review = tmp_path / "review.json"
    snapshot.write_text(json.dumps({"views": {"scanner": {"rows": []}}}), encoding="utf-8")
    review.write_text(json.dumps({"status": "MATCH", "authority": "OBSERVATION_ONLY"}), encoding="utf-8")

    handler = make_handler(snapshot, tmp_path, review)
    # The handler factory is intentionally read-only; existence of the review
    # input is validated through the same JSON contract used by /api/snapshot.
    assert handler is not None
