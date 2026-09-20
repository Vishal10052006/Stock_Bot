from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_phase9_sector_membership import (
    load_manifest,
    load_symbols,
    validate_manifest_provenance,
)


def test_load_symbols_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "symbols.txt"
    path.write_text(
        "RELIANCE\nRELIANCE\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate symbols"):
        load_symbols(path)


def test_load_symbols_normalizes_symbols(tmp_path: Path) -> None:
    path = tmp_path / "symbols.txt"
    path.write_text(
        " reliance \nTCS\n",
        encoding="utf-8",
    )

    assert load_symbols(path) == ("RELIANCE", "TCS")


def test_manifest_requires_object(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(["invalid"]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="JSON object"):
        load_manifest(path)


def test_manifest_requires_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "snapshots": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        load_manifest(path)


def test_mapping_file_requires_provenance(tmp_path: Path) -> None:
    mapping = tmp_path / "sector_membership.csv"
    mapping.write_text(
        "symbol,sector_index_symbol,effective_from,effective_to\n"
        "RELIANCE,NIFTY_OIL_AND_GAS,2026-01-01,\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": "1.0",
        "snapshots": [],
    }

    with pytest.raises(
        ValueError,
        match="manifest.snapshots is empty",
    ):
        validate_manifest_provenance(
            manifest,
            mapping,
        )
