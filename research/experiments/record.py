"""Machine-readable experiment record serialization."""
from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from research.experiments.runner import ExperimentResult


def write_experiment_record(result: ExperimentResult, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
