# Historical Archive JSONL Format

Each line is one source-native `HistoricalArchiveRecord` serialized as JSON.
This format is an ingestion boundary, not a prediction dataset.

Required fields:

- `archive_id`
- `source_id`
- `external_id`
- `title`
- `content`
- `published_at`
- `observed_at`
- `available_at`

Optional fields:

- `symbols`
- `entities`
- `language`
- `content_hash`
- `metadata`
- `archived_at`
- `schema_version`

All timestamps must be timezone-aware ISO-8601 values. `published_at`,
`observed_at`, and `available_at` are source/PIT timestamps and must be
preserved exactly through loading. `archived_at` records archive provenance
and is not a substitute for `available_at`.

The loader rejects missing fields, invalid records, duplicate `archive_id`
values, and invalid timestamp values. It never fills timestamps from the
current clock and never interpolates missing causal timestamps.