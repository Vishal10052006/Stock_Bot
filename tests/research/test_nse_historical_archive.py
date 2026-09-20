from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from research.corpus.nse_archive import NSEHistoricalArchiveClient

IST = ZoneInfo("Asia/Kolkata")


def test_nse_parser_preserves_exchange_timestamps(tmp_path):
    path = tmp_path / "nse.csv"
    path.write_text(
        "SYMBOL,SUBJECT,DETAILS,BROADCAST DATE/TIME,EXCHANGE RECEIVED TIME,EXCHANGE DISSEMINATION TIME\n"
        "ABC,Results,Revenue increased,20-Sep-2026 10:00:00,20-Sep-2026 10:00:01,20-Sep-2026 10:00:02\n",
        encoding="utf-8",
    )
    records = NSEHistoricalArchiveClient.parse_csv(
        path, archived_at=datetime(2026, 9, 21, tzinfo=IST)
    )
    record = records[0]
    assert record.source_id == "nse-corporate-filings"
    assert record.symbols == ("ABC",)
    assert record.published_at == datetime(2026, 9, 20, 10, 0, tzinfo=IST)
    assert record.observed_at == datetime(2026, 9, 20, 10, 0, 1, tzinfo=IST)
    assert record.available_at == datetime(2026, 9, 20, 10, 0, 2, tzinfo=IST)


def test_nse_parser_rejects_missing_pit_timestamp(tmp_path):
    path = tmp_path / "nse.csv"
    path.write_text(
        "SYMBOL,SUBJECT,DETAILS,BROADCAST DATE/TIME,EXCHANGE RECEIVED TIME,EXCHANGE DISSEMINATION TIME\n"
        "ABC,Results,Revenue increased,20-Sep-2026 10:00:00,,20-Sep-2026 10:00:02\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="PIT timestamp"):
        NSEHistoricalArchiveClient.parse_csv(path, archived_at=datetime(2026, 9, 21, tzinfo=IST))


def test_nse_parser_is_deterministic(tmp_path):
    path = tmp_path / "nse.csv"
    row = "ABC,Results,Revenue increased,20-Sep-2026 10:00:00,20-Sep-2026 10:00:01,20-Sep-2026 10:00:02\n"
    path.write_text(
        "SYMBOL,SUBJECT,DETAILS,BROADCAST DATE/TIME,EXCHANGE RECEIVED TIME,EXCHANGE DISSEMINATION TIME\n" + row,
        encoding="utf-8",
    )
    a = NSEHistoricalArchiveClient.parse_csv(path, archived_at=datetime(2026, 9, 21, tzinfo=IST))[0]
    b = NSEHistoricalArchiveClient.parse_csv(path, archived_at=datetime(2026, 9, 21, tzinfo=IST))[0]
    assert a.archive_id == b.archive_id
    assert a.content_hash == b.content_hash