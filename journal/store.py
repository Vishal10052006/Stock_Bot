"""AB-45 append-only trade-journal persistence."""

from __future__ import annotations

from pathlib import Path

from .models import TradeJournalRecord


class DuplicateJournalRecordError(ValueError):
    """Raised when a journal record already exists."""


class TradeJournalStore:
    """JSONL-backed append-only trade journal store."""

    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self.path = Path(path)

    def append(
        self,
        record: TradeJournalRecord,
    ) -> None:
        """Append one record after duplicate validation."""

        if not isinstance(
            record,
            TradeJournalRecord,
        ):
            raise TypeError(
                "record must be a TradeJournalRecord"
            )

        existing_ids = {
            item.journal_id
            for item in self.read_all()
        }

        if record.journal_id in existing_ids:
            raise DuplicateJournalRecordError(
                "journal record already exists: "
                f"{record.journal_id}"
            )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                record.to_json()
            )
            handle.write("\n")

    def read_all(
        self,
    ) -> tuple[TradeJournalRecord, ...]:
        """Read all journal records in append order."""

        if not self.path.exists():
            return ()

        records: list[TradeJournalRecord] = []

        with self.path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            for line_number, line in enumerate(
                handle,
                start=1,
            ):
                line = line.strip()

                if not line:
                    continue

                try:
                    import json

                    data = json.loads(line)

                    records.append(
                        TradeJournalRecord.from_dict(
                            data
                        )
                    )
                except Exception as exc:
                    raise ValueError(
                        "invalid journal record at "
                        f"line {line_number}"
                    ) from exc

        return tuple(records)

    def count(self) -> int:
        """Return the number of persisted records."""

        return len(self.read_all())
