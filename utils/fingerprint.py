"""Deterministic SHA-256 fingerprints for validation artifacts.

The helper intentionally supports only explicit, serializable structures so an
artifact identity cannot silently depend on object memory addresses.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
import hashlib
import json
import math
from typing import Any

import numpy as np
import pandas as pd


def _canonical(value: Any) -> Any:
    """Convert supported values into deterministic JSON-compatible data."""
    if value is None or isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value

    if isinstance(value, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(value).isoformat()

    if isinstance(value, Enum):
        return {
            "enum_type": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _canonical(value.value),
        }

    if isinstance(value, pd.DataFrame):
        frame = value.copy(deep=True)
        try:
            hashed = pd.util.hash_pandas_object(
                frame,
                index=True,
            ).to_numpy(dtype="uint64").tobytes()
            data_hash = hashlib.sha256(hashed).hexdigest()
        except (TypeError, ValueError):
            data_hash = hashlib.sha256(
                frame.to_json(
                    orient="split",
                    date_format="iso",
                    date_unit="ns",
                ).encode("utf-8")
            ).hexdigest()

        return {
            "type": "DataFrame",
            "shape": list(frame.shape),
            "columns": [str(column) for column in frame.columns],
            "dtypes": [str(dtype) for dtype in frame.dtypes],
            "index": [str(value) for value in frame.index],
            "data_hash": data_hash,
        }

    if isinstance(value, pd.Series):
        series = value.copy(deep=True)
        try:
            hashed = pd.util.hash_pandas_object(
                series,
                index=True,
            ).to_numpy(dtype="uint64").tobytes()
            data_hash = hashlib.sha256(hashed).hexdigest()
        except (TypeError, ValueError):
            data_hash = hashlib.sha256(
                series.to_json(
                    orient="split",
                    date_format="iso",
                    date_unit="ns",
                ).encode("utf-8")
            ).hexdigest()

        return {
            "type": "Series",
            "name": str(series.name),
            "dtype": str(series.dtype),
            "index": [str(value) for value in series.index],
            "length": len(series),
            "data_hash": data_hash,
        }

    if isinstance(value, np.ndarray):
        return {
            "type": "ndarray",
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "data_hash": hashlib.sha256(
                np.ascontiguousarray(value).tobytes()
            ).hexdigest(),
        }

    if isinstance(value, np.generic):
        return _canonical(value.item())

    if is_dataclass(value):
        return {
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                field.name: _canonical(getattr(value, field.name))
                for field in fields(value)
            },
        }

    if isinstance(value, dict):
        return {
            str(key): _canonical(item)
            for key, item in sorted(
                value.items(),
                key=lambda item: str(item[0]),
            )
        }

    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]

    raise TypeError(
        "unsupported value for deterministic artifact fingerprint: "
        f"{type(value).__module__}.{type(value).__qualname__}"
    )


def artifact_fingerprint(value: Any) -> str:
    """Return a deterministic SHA-256 identity for a supported artifact."""
    canonical = json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
