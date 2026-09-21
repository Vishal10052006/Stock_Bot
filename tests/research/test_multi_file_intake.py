from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from research.corpus.multi_intake import ingest_nse_csv_files

IST = ZoneInfo("Asia/Kolkata")


def _write_csv(path: Path, rows: str) -> None:
    path.write_text(
        "SYMBOL,SUBJECT,DETAILS,BROADCAST DATE/TIME,EXCHANGE RECEIVED TIME,EXCHANGE DISSEMINATION TIME\n"
        + rows,
        encoding="utf-8",
    )


def test_multi_file_intake_deduplicates_overlapping_archives(tmp_path: Path):
    row_a = (
        "ABC,Results,Revenue increased,20-Sep-2026 10:00:00,"
        "20-Sep-2026 10:00:01,20-Sep-2026 10:00:02\n"
    )
    row_b = (
        "XYZ,Guidance,Outlook improved,20-Sep-2026 11:00:00,"
        "20-Sep-2026 11:00:01,20-Sep-2026 11:00:02\n"
    )
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    _write_csv(first, row_a)
    _write_csv(second, row_a + row_b)

    result = ingest_nse_csv_files(
        (first, second),
        archive_jsonl_path=tmp_path / "archive.jsonl",
        manifest_path=tmp_path / "manifest.json",
        dataset_id="nse-test",
        version="multi-2026-09-20",
        accessed_at=datetime(2026, 9, 21, tzinfo=IST),
        archived_at=datetime(2026, 9, 21, tzinfo=IST),
    )

    assert result.archive_record_count == 3
    assert result.audit.accepted_documents == 2
    assert result.audit.duplicate_documents == 1
    assert result.corpus.document_count == 2
    assert len(result.raw_collection_sha256) == 64
