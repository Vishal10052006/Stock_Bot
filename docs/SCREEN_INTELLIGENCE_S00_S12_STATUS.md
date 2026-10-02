# STOCK_BOT Screen Intelligence S00-S13 Status

## Architecture

Wayland desktop -> XDG ScreenCast -> PipeWire -> GStreamer -> RGB ScreenFrame

ScreenFrame -> Window/Chart Detection -> OCR / Candle / Indicator / Timeframe Evidence
-> S13 Evidence Validation -> Visual Context -> Screen/Market Reconciliation
-> Confidence Gate -> Screen-Aware Analysis

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
| S05 | Chart recognition | COMPLETE | REAL + regression tests |
| S06 | Candle visual evidence | COMPLETE | REAL smoke |
| S07 | Indicator evidence | COMPLETE | REAL smoke |
| S08 | Timeframe evidence | COMPLETE | REAL smoke |
| S09 | Visual-context contract | COMPLETE | REAL smoke |
| S10 | Screen/market reconciliation | COMPLETE | REAL smoke |
| S11 | Screen confidence gate | COMPLETE | REAL smoke |
| S12 | Screen-aware analysis context | COMPLETE | REAL smoke |
| S13 | Evidence validation/hardening | COMPLETE | Deterministic unit tests + live smoke |

## S13 validation and hardening

S13 validates one ScreenObservation before screen-aware analysis can mark it usable.
It checks chart presence and geometry, chart and overall confidence, required
symbol/timeframe presence for screen-aware analysis, canonical timeframe syntax,
candle count/density sanity, structured candle consistency, structured timeframe
evidence, and OCR status.

Invalid evidence fails closed. S13 never repairs OCR, invents market values,
infers OHLC, creates signals, or authorizes orders.

## Safety boundaries

- Market feed remains authoritative for structured market values.
- Screen observations are contextual evidence.
- Future screen observations are rejected.
- Stale screen observations are rejected.
- Symbol/timeframe mismatches are explicit.
- Low chart/overall confidence blocks screen usability.
- S13 invalid evidence blocks screen-aware usability.
- S12 produces analysis context only; it has no order/risk/execution authority.
- No exact OHLC values are fabricated from pixels.

## Validation commands

Unit/regression:

    pytest -q tests/screen_observer

Full screen intelligence smoke:

    python scripts/test_screen_intelligence_s06_s12.py

Full repository:

    pytest -q

The live smoke test requires a real TradingView/browser window and validates the
Wayland ScreenCast -> PipeWire -> visual evidence -> S13 validation ->
reconciliation -> confidence -> screen-aware analysis path.
