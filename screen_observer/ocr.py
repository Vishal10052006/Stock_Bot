"""Structured OCR engine for Screen Observer S04.

Observation-only: preserves capture time, token confidence, and bounding boxes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

import pandas as pd


def _timestamp(value: pd.Timestamp | datetime) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        raise ValueError("OCR timestamps must be timezone-aware")
    return ts


@dataclass(frozen=True, slots=True)
class OCRToken:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int
    block_num: int = 0
    line_num: int = 0
    word_num: int = 0

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("OCR token text must not be empty")
        if not 0.0 <= float(self.confidence) <= 100.0:
            raise ValueError("OCR token confidence must be in [0, 100]")
        if min(self.left, self.top) < 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("OCR token geometry is invalid")

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)


@dataclass(frozen=True, slots=True)
class OCRResult:
    observed_at: pd.Timestamp
    raw_text: str = ""
    tokens: tuple[OCRToken, ...] = ()
    lines: tuple[str, ...] = ()
    confidence: float = 0.0
    status: str = "ok"
    region: tuple[int, int, int, int] | None = None
    error: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at))
        object.__setattr__(self, "tokens", tuple(self.tokens))
        object.__setattr__(
            self, "lines", tuple(x for x in self.lines if x.strip())
        )
        object.__setattr__(self, "metadata", dict(self.metadata))
        if not 0.0 <= float(self.confidence) <= 100.0:
            raise ValueError("OCR confidence must be in [0, 100]")
        if self.status not in {"ok", "unavailable", "failed"}:
            raise ValueError("invalid OCR status")
        if self.region is not None and (
            len(self.region) != 4 or any(int(x) < 0 for x in self.region)
        ):
            raise ValueError("OCR region must contain four non-negative values")

    @property
    def available(self) -> bool:
        return self.status == "ok"

    @property
    def text(self) -> tuple[str, ...]:
        return self.lines

    def as_dict(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at.isoformat(),
            "raw_text": self.raw_text,
            "lines": list(self.lines),
            "confidence": self.confidence,
            "status": self.status,
            "region": self.region,
            "tokens": [
                {
                    "text": t.text,
                    "confidence": t.confidence,
                    "bbox": t.bbox,
                    "block_num": t.block_num,
                    "line_num": t.line_num,
                    "word_num": t.word_num,
                }
                for t in self.tokens
            ],
            "error": self.error,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class OCRConfig:
    psm: int = 11
    scale: int = 2
    min_token_confidence: float = 0.0
    language: str = "eng"

    def __post_init__(self) -> None:
        if self.psm < 3 or self.scale < 1:
            raise ValueError("invalid OCR psm/scale")
        if not 0.0 <= self.min_token_confidence <= 100.0:
            raise ValueError("OCR minimum confidence must be in [0, 100]")
        if not self.language.strip():
            raise ValueError("OCR language must not be empty")


def _prepare_image(image: Any, scale: int):
    from PIL import Image, ImageOps

    if isinstance(image, Image.Image):
        pil = image.convert("RGB")
    else:
        import numpy as np
        array = np.asarray(image)
        if array.ndim == 2:
            pil = Image.fromarray(array.astype("uint8"), mode="L").convert("RGB")
        elif array.ndim == 3 and array.shape[2] in (3, 4):
            pil = Image.fromarray(array[:, :, :3].astype("uint8"), mode="RGB")
        else:
            raise ValueError("image must be grayscale, RGB, or RGBA")

    pil = ImageOps.autocontrast(pil.convert("L")).convert("RGB")
    if scale != 1:
        pil = pil.resize(
            (pil.width * scale, pil.height * scale),
            Image.Resampling.LANCZOS,
        )
    return pil


def _confidence(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if result < 0 else min(100.0, result)


def ocr_image(
    image: Any,
    *,
    observed_at: pd.Timestamp | datetime,
    region: tuple[int, int, int, int] | None = None,
    config: OCRConfig | None = None,
) -> OCRResult:
    """Run Tesseract; unavailable/failed states never invent text."""

    cfg = config or OCRConfig()
    timestamp = _timestamp(observed_at)

    try:
        import pytesseract
        from pytesseract import Output
        pytesseract.get_tesseract_version()
    except ImportError:
        return OCRResult(
            observed_at=timestamp,
            status="unavailable",
            region=region,
            error="pytesseract is not installed",
        )
    except Exception as exc:
        return OCRResult(
            observed_at=timestamp,
            status="unavailable",
            region=region,
            error=f"Tesseract unavailable: {type(exc).__name__}: {exc}",
        )

    try:
        data = pytesseract.image_to_data(
            _prepare_image(image, cfg.scale),
            lang=cfg.language,
            config=f"--psm {cfg.psm}",
            output_type=Output.DICT,
        )
    except Exception as exc:
        return OCRResult(
            observed_at=timestamp,
            status="failed",
            region=region,
            error=f"{type(exc).__name__}: {exc}",
        )

    tokens: list[OCRToken] = []
    grouped: dict[tuple[int, int], list[str]] = {}
    text_values = data.get("text", [])
    count = len(text_values)

    def get(name: str, index: int, default: Any) -> Any:
        values = data.get(name)
        return values[index] if values is not None and index < len(values) else default

    for i in range(count):
        text = str(text_values[i]).strip()
        conf = _confidence(get("conf", i, -1))
        if not text or conf is None:
            continue
        try:
            left, top = int(get("left", i, 0)), int(get("top", i, 0))
            width, height = int(get("width", i, 0)), int(get("height", i, 0))
            block = int(get("block_num", i, 0))
            line = int(get("line_num", i, 0))
            word = int(get("word_num", i, 0))
        except (TypeError, ValueError):
            continue
        if width <= 0 or height <= 0:
            continue

        if cfg.scale != 1:
            left //= cfg.scale
            top //= cfg.scale
            width = max(1, width // cfg.scale)
            height = max(1, height // cfg.scale)

        token = OCRToken(
            text=text,
            confidence=conf,
            left=left,
            top=top,
            width=width,
            height=height,
            block_num=block,
            line_num=line,
            word_num=word,
        )
        tokens.append(token)
        if conf >= cfg.min_token_confidence:
            grouped.setdefault((block, line), []).append(text)

    lines = tuple(" ".join(words) for _, words in sorted(grouped.items()))
    return OCRResult(
        observed_at=timestamp,
        raw_text="\n".join(lines),
        tokens=tuple(tokens),
        lines=lines,
        confidence=round(
            sum(t.confidence for t in tokens) / len(tokens), 2
        ) if tokens else 0.0,
        status="ok",
        region=region,
        metadata={
            "engine": "tesseract",
            "language": cfg.language,
            "psm": str(cfg.psm),
            "scale": str(cfg.scale),
        },
    )
