# Upstox Instrument Resolution

The execution engine accepts the broker-neutral stock symbol. The Upstox adapter resolves that symbol to an exact provider instrument identity.

## Flow

RELIANCE / TCS / ITC
→ Upstox instrument search
→ exact NSE/EQ trading-symbol match
→ canonical instrument_key
→ Upstox order payload

The user does not need to manually enter a new instrument key every time the company changes.

## Safety rules

- Only exact trading-symbol matches are accepted.
- Requested exchange and segment must match the returned record.
- Zero matches fail closed.
- Multiple exact matches with different instrument keys fail closed.
- The resolver caches a successfully resolved symbol for the resolver lifetime.
- Read-only instrument search is separate from order submission.
- No live-order authorization is created by instrument resolution.

## Integration

execution/adapters/upstox_instruments.py provides the broker-facing resolution contract.

execution/adapters/upstox_instrument_search.py provides the read-only Upstox search transport.

The existing UpstoxBrokerAdapter remains responsible for converting the resolved identifier into the provider-specific order payload.

## Current limitation

The current implementation introduces the resolver but does not silently replace the existing adapter wiring. The next integration step is to inject the resolver into the adapter/application composition root and remove manual token configuration from the normal company-selection path.

Live execution remains locked.
