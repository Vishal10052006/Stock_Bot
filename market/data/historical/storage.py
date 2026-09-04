"""Deterministic persistence for validated historical datasets."""

from __future__ import annotations

import json
from datetime import datetime
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from market.candles.models import Candle
from market.data.historical.models import HistoricalDataset


class HistoricalDatasetStore:
    """Interface for persistent historical dataset storage."""

    def save(
        self,
        dataset: HistoricalDataset,
        path: str | Path,
    ) -> None:
        """Persist a historical dataset."""
        raise NotImplementedError

    def load(
        self,
        path: str | Path,
    ) -> HistoricalDataset:
        """Load a historical dataset."""
        raise NotImplementedError


class JsonHistoricalDatasetStore(HistoricalDatasetStore):
    """Persist HistoricalDataset objects as deterministic JSON."""

    SCHEMA_VERSION = "1"

    @staticmethod
    def _serialize(dataset: HistoricalDataset) -> dict:
        """Convert a canonical dataset into a JSON-safe payload."""

        return {
            "schema_version": JsonHistoricalDatasetStore.SCHEMA_VERSION,
            "symbol": dataset.symbol,
            "exchange": dataset.exchange,
            "timeframe_minutes": dataset.timeframe_minutes,
            "metadata": dict(sorted(dataset.metadata.items())),
            "bars": [
                {
                    "symbol": bar.symbol,
                    "exchange": bar.exchange,
                    "timeframe_minutes": bar.timeframe_minutes,
                    "timestamp": bar.timestamp.isoformat(),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in dataset.bars
            ],
        }

    @staticmethod
    def _deserialize(payload: object) -> HistoricalDataset:
        """Reconstruct a canonical dataset from a JSON payload."""

        if not isinstance(payload, dict):
            raise ValueError(
                "historical dataset artifact must contain a JSON object"
            )

        if payload.get("schema_version") != JsonHistoricalDatasetStore.SCHEMA_VERSION:
            raise ValueError(
                "unsupported historical dataset schema version"
            )

        required_fields = (
            "symbol",
            "exchange",
            "timeframe_minutes",
            "bars",
        )

        missing = [
            field
            for field in required_fields
            if field not in payload
        ]

        if missing:
            raise ValueError(
                f"historical dataset artifact is missing fields: {missing}"
            )

        raw_bars = payload["bars"]

        if not isinstance(raw_bars, list):
            raise ValueError(
                "historical dataset bars must be a JSON list"
            )

        bars: list[Candle] = []

        for index, raw_bar in enumerate(raw_bars):
            if not isinstance(raw_bar, dict):
                raise ValueError(
                    f"historical dataset bar {index} must be a JSON object"
                )

            try:
                bars.append(
                    Candle(
                        symbol=raw_bar["symbol"],
                        exchange=raw_bar["exchange"],
                        timeframe_minutes=raw_bar[
                            "timeframe_minutes"
                        ],
                        timestamp=datetime.fromisoformat(
                            raw_bar["timestamp"]
                        ),
                        open=raw_bar["open"],
                        high=raw_bar["high"],
                        low=raw_bar["low"],
                        close=raw_bar["close"],
                        volume=raw_bar["volume"],
                    )
                )
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    f"invalid historical dataset bar at index {index}"
                ) from exc

        try:
            metadata = payload.get("metadata", {})

            if not isinstance(metadata, dict):
                raise ValueError(
                    "historical dataset metadata must be a JSON object"
                )

            return HistoricalDataset(
                symbol=payload["symbol"],
                exchange=payload["exchange"],
                timeframe_minutes=payload["timeframe_minutes"],
                bars=tuple(bars),
                metadata=metadata,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "invalid historical dataset artifact"
            ) from exc

    def save(
        self,
        dataset: HistoricalDataset,
        path: str | Path,
    ) -> None:
        """Persist a dataset using deterministic atomic replacement."""

        if not isinstance(dataset, HistoricalDataset):
            raise TypeError(
                "dataset must be a HistoricalDataset"
            )

        destination = Path(path)

        if destination.exists() and destination.is_dir():
            raise ValueError(
                "historical dataset path must be a file"
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._serialize(dataset)

        content = (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n"
        )

        temporary_path: Path | None = None

        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)

            os.replace(
                temporary_path,
                destination,
            )
            temporary_path = None

        finally:
            if temporary_path is not None:
                temporary_path.unlink(
                    missing_ok=True,
                )

    def load(
        self,
        path: str | Path,
    ) -> HistoricalDataset:
        """Load and reconstruct a historical dataset artifact."""

        source = Path(path)

        if not source.exists():
            raise FileNotFoundError(
                f"historical dataset does not exist: {source}"
            )

        if not source.is_file():
            raise ValueError(
                "historical dataset path must be a file"
            )

        try:
            payload = json.loads(
                source.read_text(
                    encoding="utf-8",
                )
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "unable to read historical dataset artifact"
            ) from exc

        return self._deserialize(payload)
