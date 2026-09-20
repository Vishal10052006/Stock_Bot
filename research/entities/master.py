"""Versioned production entity master loader."""
from __future__ import annotations
import csv
from pathlib import Path


class EntityMaster:
    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = {k.strip().upper(): v.strip().upper() for k, v in mapping.items()}

    @classmethod
    def from_csv(cls, path: str | Path) -> "EntityMaster":
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            mapping = {}
            for row in csv.DictReader(handle):
                symbol = str(row.get("symbol") or row.get("nse_symbol") or "").strip().upper()
                if not symbol:
                    continue
                for value in (row.get("company_name"), row.get("name"), row.get("isin")):
                    if value:
                        mapping[str(value).strip()] = symbol
            return cls(mapping)

    def resolve(self, value: str) -> str | None:
        return self._mapping.get(value.strip().upper())
