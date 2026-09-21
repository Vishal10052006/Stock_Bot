"""CLI for combining downloaded NSE historical Research archives."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from research.corpus.multi_intake import ingest_nse_csv_files

IST = ZoneInfo("Asia/Kolkata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "csv_paths",
        nargs="+",
        help="Downloaded NSE corporate-filings CSV files.",
    )
    parser.add_argument("--dataset-id", default="nse-corporate-announcements")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", default="data/research_archive")
    parser.add_argument("--start", help="Optional corpus publication start: YYYY-MM-DD")
    parser.add_argument("--end", help="Optional corpus publication end: YYYY-MM-DD")
    args = parser.parse_args()

    time_start = (
        datetime.fromisoformat(args.start).replace(tzinfo=IST)
        if args.start else None
    )
    time_end = (
        datetime.fromisoformat(args.end).replace(tzinfo=IST)
        if args.end else None
    )
    now = datetime.now(IST)
    output_dir = Path(args.output_dir)

    result = ingest_nse_csv_files(
        args.csv_paths,
        archive_jsonl_path=output_dir / "historical_archive.jsonl",
        manifest_path=output_dir / "manifest.json",
        dataset_id=args.dataset_id,
        version=args.version,
        accessed_at=now,
        archived_at=now,
        time_start=time_start,
        time_end=time_end,
    )

    print(f"input files: {len(result.inputs)}")
    print(f"archive records: {result.archive_record_count}")
    print(f"accepted documents: {result.audit.accepted_documents}")
    print(f"duplicates: {result.audit.duplicate_documents}")
    print(f"rejected documents: {result.audit.rejected_documents}")
    print(f"corpus documents: {result.corpus.document_count}")
    print(f"corpus fingerprint: {result.corpus.fingerprint}")
    print(f"raw collection sha256: {result.raw_collection_sha256}")


if __name__ == "__main__":
    main()
