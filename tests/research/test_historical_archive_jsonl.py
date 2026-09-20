from datetime import datetime, timezone

import pytest

from research.corpus.archive_jsonl import HistoricalArchiveJsonlLoader

UTC = timezone.utc


def _line(**overrides):
    row = {
        "archive_id": "a1",
        "source_id": "source-a",
        "external_id": "x1",
        "title": "Historical event",
        "content": "Revenue increased.",
        "published_at": "2026-01-01T10:00:00+00:00",
        "observed_at": "2026-01-01T10:01:00+00:00",
        "available_at": "2026-01-01T10:02:00+00:00",
        "archived_at": "2026-02-01T00:00:00+00:00",
        "symbols": ["ABC"],
        "entities": ["ABC Corp"],
        "metadata": {"source_reference": "https://example.test/a1"},
    }
    row.update(overrides)
    return row


def test_loader_preserves_source_timestamps(tmp_path):
    path = tmp_path / "archive.jsonl"
    path.write_text(__import__("json").dumps(_line()) + "\n", encoding="utf-8")

    record = HistoricalArchiveJsonlLoader().load(path)[0]

    assert record.published_at == datetime(2026, 1, 1, 10, tzinfo=UTC)
    assert record.observed_at == datetime(2026, 1, 1, 10, 1, tzinfo=UTC)
    assert record.available_at == datetime(2026, 1, 1, 10, 2, tzinfo=UTC)
    assert record.archived_at == datetime(2026, 2, 1, tzinfo=UTC)
    assert record.symbols == ("ABC",)


def test_loader_rejects_missing_required_field(tmp_path):
    import json
    row = _line()
    del row["available_at"]
    path = tmp_path / "archive.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        HistoricalArchiveJsonlLoader().load(path)


def test_loader_rejects_duplicate_archive_id(tmp_path):
    import json
    row = _line()
    path = tmp_path / "archive.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate archive_id"):
        HistoricalArchiveJsonlLoader().load(path)


def test_loader_rejects_invalid_timestamp(tmp_path):
    import json
    row = _line(published_at="not-a-timestamp")
    path = tmp_path / "archive.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        HistoricalArchiveJsonlLoader().load(path)