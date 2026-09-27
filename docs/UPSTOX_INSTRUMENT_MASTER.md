# Upstox Instrument Master

Upstox provides daily refreshed BOD instrument data in JSON format. Upstox recommends JSON for programmatic processing and recommends instrument_key as the unique identifier.

## Stock Bot design

The execution path should resolve:

symbol → local current instrument master → exact NSE_EQ/EQ record → instrument_key

The local master is therefore the primary resolution source for normal company changes. The Instrument Search API remains an optional fallback/discovery path and is not required for every order.

## File

The resolver accepts a local JSON or gzip-compressed JSON file containing BOD instrument records.

For NSE equities, records are retained only when:

- segment = NSE_EQ
- exchange = NSE
- instrument_type = EQ

The loader preserves instrument_key, trading_symbol, ISIN, and exchange_token.

## Safety

Ambiguous symbols fail closed. Missing symbols fail closed. Non-NSE-equity records are ignored. No order is submitted during instrument-master loading or lookup.

The instrument file should be refreshed from the official Upstox source as part of the market-data/reference-data lifecycle rather than committed to source control as a static copy.

Live trading authorization is unaffected by instrument resolution.
