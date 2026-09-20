"""CLI for downloading and materializing an NSE historical Research corpus."""
from __future__ import annotations

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from research.corpus.intake import ingest_nse_csv
from research.corpus.nse_archive import NSEHistoricalArchiveClient

IST = ZoneInfo("Asia/Kolkata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="YYYY-MM-DD in Asia/Kolkata")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD in Asia/Kolkata")
    parser.add_argument("--dataset-id", default="nse-corporate-announcements")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", default="data/research_archive")
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=IST)
    end = datetime.fromisoformat(args.end).replace(tzinfo=IST)
    client = NSEHistoricalArchiveClient()
    raw_path = f"{args.output_dir}/nse_announcements.csv"
    client.download_csv(start=start, end=end, output_path=raw_path)
    now = datetime.now(IST)
    result = ingest_nse_csv(
        raw_path,
        archive_jsonl_path=f"{args.output_dir}/historical_archive.jsonl",
        manifest_path=f"{args.output_dir}/manifest.json",
        dataset_id=args.dataset_id,
        version=args.version,
        accessed_at=now,
        archived_at=now,
    )
    print(f"archive records: {result.archive_record_count}")
    print(f"accepted documents: {result.audit.accepted_documents}")
    print(f"rejected documents: {result.audit.rejected_documents}")
    print(f"corpus fingerprint: {result.corpus.fingerprint}")
    print(f"raw sha256: {result.raw_sha256}")


if __name__ == "__main__":
    main()