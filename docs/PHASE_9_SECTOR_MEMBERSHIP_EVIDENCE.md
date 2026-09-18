# Phase 9 — Point-in-Time Sector Membership Evidence

## Purpose

Phase 9 uses sector-index context only when stock-to-sector membership is established point-in-time. Current constituent lists must not be backfilled into historical dates.

Research dates:
- 2026-06-29
- 2026-07-15
- 2026-08-05
- 2026-08-26
- 2026-09-11

## Evidence chain established

### 2026-02-23 — periodic sector review

NSE Indices published a replacement notice on February 23, 2026. The changes were effective March 30, 2026 (close of March 27).

Relevant sector-index evidence:
- Nifty Financial Services: ICICI Prudential Life (ICICIPRULI) excluded and Max Financial Services (MFSL) included.
- Nifty Oil & Gas: Gujarat Gas (GUJGASLTD) excluded and Chennai Petroleum (CHENNPETRO) included.
- Nifty Realty: Signatureglobal (SIGNATURE) excluded and Aditya Birla Real Estate (ABREL) included.
- The notice explicitly states that no changes were made in Nifty Auto, Nifty Bank, Nifty Chemicals, Nifty FMCG, Nifty Healthcare, Nifty IT, Nifty Media, Nifty Metal, Nifty Pharma, Nifty Private Bank, and Nifty PSU Bank.

Source:
https://www.niftyindices.com/Press_Release/ind_prs23022026.pdf

### 2026-04-23 — Vedanta demerger

NSE Indices published a corporate-action adjustment for Vedanta. Four resulting entities were temporarily represented with dummy symbols in several indices, including Nifty Metal, effective April 30, 2026.

Source:
https://www.niftyindices.com/Press_Release/ind_prs23042026.pdf

### 2026-06-17 — Vedanta follow-up

NSE Indices subsequently excluded Vedanta Power (VEDPOWER) and Vedanta Iron and Steel (VISL) from various indices, including Nifty Metal, effective June 19, 2026.

Source:
https://www.niftyindices.com/Press_Release/ind_prs17062026.pdf

### Other 2026 notices inspected

The June 10 notice concerns strategy-index changes and criteria revisions rather than the Phase 9 sector-index membership baseline.

Source:
https://www.niftyindices.com/Press_Release/ind_prs10062026.pdf

The July 13 notice includes a Nifty Pharma replacement caused by the amalgamation of J.B. Chemicals & Pharmaceuticals into Torrent Pharmaceuticals, effective July 17, 2026. Neither affected symbol is present in the current 70-symbol Phase 9 universe, so this event does not add a mapping for the current sample.

Source:
https://www.niftyindices.com/Press_Release/ind_prs13072026_1.pdf

The July 17 notice for changes effective July 31 concerns ESG/Shariah indices and does not establish a Phase 9 sector-index membership change.

Source:
https://www.niftyindices.com/Press_Release/ind_prs17072026_1.pdf

## Authoritative-data boundary

NSE Indices exposes historical index-level data publicly, but its data-subscription documentation states that index constituent data is a separate data product and is available through subscription/data vendors. Therefore the public press-release archive does not provide a complete historical constituent snapshot for every sector index and every Phase 9 research date.

Sources:
https://www.niftyindices.com/reports
https://www.niftyindices.com/offerings/data-subscription

Consequences for Phase 9:
1. Dated inclusion/exclusion events can be encoded as authoritative membership events.
2. Explicit no-change statements can preserve an already established baseline.
3. A complete baseline must come from an authoritative historical constituent snapshot; it must not be synthesized from today's constituent list.
4. Symbols without provable historical membership remain unresolved.
5. The dataset builder must fail or preserve missing sector context rather than silently fabricating membership.

## Reconstitution cadence

NSE Indices' reconstitution calendar states that Nifty Auto and Nifty Bank are reviewed semi-annually on the last working day of March and September. The calendar is part of the evidence chain, but it does not replace constituent evidence or corporate-action notices.

Source:
https://niftyindices.com/resources/index-rebalancing-schedule

## Current status

The PIT resolver and validation infrastructure are implemented. Historical membership data remains intentionally unpopulated until the evidence chain is complete enough to support each mapping.

This is a deliberate data-integrity gate, not a missing implementation.