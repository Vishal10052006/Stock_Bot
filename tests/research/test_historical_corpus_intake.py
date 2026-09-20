from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from research.corpus.intake import ingest_nse_csv

IST = ZoneInfo("Asia/Kolkata")


def test_nse_intake_writes_reproducible_outputs(tmp_path: Path):
    csv_path = tmp_path / "source.csv"
    csv_path.write_text(
        "SYMBOL,SUBJECT,DETAILS,BROADCAST DATE/TIME,EXCHANGE RECEIVED TIME,EXCHANGE DISSEMINATION TIME\n"
        "ABC,Results,Revenue increased,20-Sep-2026 10:00:00,20-Sep-2026 10:00:01,20-Sep-2026 10:00:02\n",
        encoding="utf-8",
    )

    result = ingest_nse_csv(
        csv_path,
        archive_jsonl_path=tmp_path / "archive.jsonl",
        manifest_path=tmp_path / "manifest.json",
        dataset_id="nse-test",
        version="2026-09-20",
        accessed_at=datetime(2026, 9, 21, tzinfo=IST),
        archived_at=datetime(2026, 9, 21, tzinfo=IST),
    )

    assert result.archive_record_count == 1
    assert result.audit.accepted_documents == 1
    assert len(result.corpus.fingerprint) == 64
    assert result.raw_sha256
    assert (tmp_path / "archive.jsonl").exists()
    assert (tmp_path / "manifest.json").exists()
