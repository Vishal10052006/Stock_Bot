# STOCK_BOT Screen Intelligence S00-S12 Status

## Architecture

Wayland desktop -> XDG ScreenCast -> PipeWire -> GStreamer -> RGB ScreenFrame

ScreenFrame -> Window/Chart Detection -> OCR / Candle / Indicator / Timeframe Evidence
-> Visual Context -> Screen/Market Reconciliation -> Confidence Gate -> Screen-Aware Analysis

The entire Screen Intelligence layer is observation-only. It does not authorize trades,
size positions, modify risk, or submit broker orders.

## Status

| Stage | Capability | Implementation | Validation |
|---|---|---:|---:|
| S00 | Screen capture | COMPLETE | REAL |
| S01 | Capture scheduler/runtime | COMPLETE | REAL |
| S02 | Window detection | COMPLETE | REAL portal/window selection |
| S03 | Wayland/PipeWire capture | COMPLETE | REAL 1920x1200 RGB stream |
| S04 | Structured OCR | COMPLETE | REAL Tesseract smoke |
| S05 | Chart recognition | COMPLETE | REAL + 13 regression tests |
| S06 | Candle visual evidence | COMPLETE | PENDING local full smoke |
| S07 | Indicator evidence | COMPLETE | PENDING local full smoke |
| S08 | Timeframe evidence | COMPLETE | PENDING local full smoke |
| S09 | Visual-context contract | COMPLETE | PENDING local full smoke |
| S10 | Screen/market reconciliation | COMPLETE | PENDING local full smoke |
| S11 | Screen confidence gate | COMPLETE | PENDING local full smoke |
| S12 | Screen-aware analysis context | COMPLETE | PENDING local full smoke |

## Safety boundaries

- Market feed remains authoritative for structured market values.
- Screen observations are contextual evidence.
- Future screen observations are rejected.
- Stale screen observations are rejected.
- Symbol/timeframe mismatches are explicit.
- Low chart confidence blocks screen usability.
- S12 produces analysis context only; it has no order/risk/execution authority.
- No exact OHLC values are fabricated from pixels.

## Validation commands

Unit/regression:

    pytest -q tests/screen_observer

Full screen intelligence smoke:

    python scripts/test_screen_intelligence_s06_s12.py

The S06-S12 smoke test requires a real TradingView/browser window and validates the
Wayland ScreenCast -> PipeWire -> visual evidence -> reconciliation -> confidence ->
analysis path.
