from datetime import datetime, timezone
from pathlib import Path

from research.corpus.nse_archive import NSEHistoricalArchiveClient

UTC = timezone.utc


def _write_csv(path: Path, rows: list[str]) -> None:
    path.write_text(
        "SYMBOL,SUBJECT,DETAILS,BROADCAST DATE/TIME,EXCHANGE RECEIVED TIME,EXCHANGE DISSEMINATION TIME,ID\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )


def test_nse_archive_identity_distinguishes_symbols_with_same_external_id(tmp_path):
    path = tmp_path / "nse.csv"
    _write_csv(
        path,
        [
            "AAA,Result,Revenue increased,01-Jan-2026 10:00:00,01-Jan-2026 10:01:00,01-Jan-2026 10:02:00,ATT-1",
            "BBB,Result,Revenue increased,01-Jan-2026 10:00:00,01-Jan-2026 10:01:00,01-Jan-2026 10:02:00,ATT-1",
        ],
    )

    records = NSEHistoricalArchiveClient.parse_csv(
        path,
        archived_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert len(records) == 2
    assert records[0].archive_id != records[1].archive_id


def test_nse_archive_identity_distinguishes_timestamped_records(tmp_path):
    path = tmp_path / "nse.csv"
    _write_csv(
        path,
        [
            "AAA,Result,Revenue increased,01-Jan-2026 10:00:00,01-Jan-2026 10:01:00,01-Jan-2026 10:02:00,ATT-1",
            "AAA,Result,Revenue increased,01-Jan-2026 11:00:00,01-Jan-2026 11:01:00,01-Jan-2026 11:02:00,ATT-1",
        ],
    )

    records = NSEHistoricalArchiveClient.parse_csv(
        path,
        archived_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert len(records) == 2
    assert records[0].archive_id != records[1].archive_id
