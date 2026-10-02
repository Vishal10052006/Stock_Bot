from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from PIL import Image

from screen_observer.ocr import OCRConfig, OCRResult, OCRToken, ocr_image


def test_ocr_token_contract_and_bbox():
    token = OCRToken(
        text="NSE:RELIANCE",
        confidence=96.5,
        left=10,
        top=20,
        width=100,
        height=24,
    )
    assert token.bbox == (10, 20, 100, 24)


def test_ocr_result_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        OCRResult(observed_at=datetime.now())


def test_ocr_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        OCRConfig(psm=2)
    with pytest.raises(ValueError):
        OCRConfig(scale=0)
    with pytest.raises(ValueError):
        OCRConfig(min_token_confidence=101)


def test_ocr_image_structures_tesseract_data(monkeypatch):
    fake = SimpleNamespace(
        Output=SimpleNamespace(DICT="dict"),
        get_tesseract_version=lambda: "5.0",
        image_to_data=lambda image, lang, config, output_type: {
            "text": ["NSE:RELIANCE", "5m", ""],
            "conf": ["96.0", "90.0", "-1"],
            "left": [20, 220, 0],
            "top": [10, 30, 0],
            "width": [160, 40, 0],
            "height": [24, 20, 0],
            "block_num": [1, 1, 0],
            "line_num": [1, 1, 0],
            "word_num": [1, 2, 0],
        },
    )
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", fake)

    observed_at = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
    result = ocr_image(
        Image.new("RGB", (400, 100), "white"),
        observed_at=observed_at,
        config=OCRConfig(scale=2),
    )

    assert result.status == "ok"
    assert result.lines == ("NSE:RELIANCE 5m",)
    assert result.raw_text == "NSE:RELIANCE 5m"
    assert result.confidence == 93.0
    assert result.observed_at == observed_at
    assert result.tokens[0].bbox == (10, 5, 80, 12)
    assert result.tokens[1].bbox == (110, 15, 20, 10)
    assert result.metadata["engine"] == "tesseract"


def test_ocr_image_filters_lines_by_minimum_confidence(monkeypatch):
    fake = SimpleNamespace(
        Output=SimpleNamespace(DICT="dict"),
        get_tesseract_version=lambda: "5.0",
        image_to_data=lambda **kwargs: {
            "text": ["RELIANCE", "garbled"],
            "conf": ["95", "20"],
            "left": [0, 50],
            "top": [0, 0],
            "width": [80, 40],
            "height": [20, 20],
            "block_num": [1, 1],
            "line_num": [1, 1],
            "word_num": [1, 2],
        },
    )
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", fake)

    result = ocr_image(
        Image.new("RGB", (200, 60), "white"),
        observed_at="2026-10-02T10:00:00+00:00",
        config=OCRConfig(scale=1, min_token_confidence=80),
    )

    assert result.lines == ("RELIANCE",)
    assert len(result.tokens) == 2
    assert result.confidence == 57.5


def test_ocr_image_returns_failed_without_inventing_text(monkeypatch):
    fake = SimpleNamespace(
        Output=SimpleNamespace(DICT="dict"),
        get_tesseract_version=lambda: "5.0",
        image_to_data=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", fake)

    result = ocr_image(
        Image.new("RGB", (200, 60), "white"),
        observed_at="2026-10-02T10:00:00+00:00",
    )

    assert result.status == "failed"
    assert result.lines == ()
    assert result.raw_text == ""
    assert result.confidence == 0.0
    assert "boom" in (result.error or "")
