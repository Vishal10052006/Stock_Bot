# Phase 25 — Broker Integration

Phase 25 establishes the provider-specific Upstox contract while keeping live execution locked.

Upstox currently documents a V3 Place Order endpoint and sandbox support. The V3 order request includes quantity, product, validity, price, tag, instrument token, order type, transaction type, disclosed quantity, trigger price, AMO, slicing, and market protection.

`UpstoxBrokerAdapter` maps the broker-neutral `OrderRequest` into the provider payload and converts provider responses into canonical execution snapshots.

Credentials are not stored in the adapter. The provider client is injected.

Enabled mode requires `sandbox=True`; the default is disabled.

Before any live activation, the repository still requires current broker/API verification, sandbox lifecycle testing, reconciliation verification, authentication verification, compliance verification, and complete readiness evidence.

Phase 25 engineering infrastructure is implemented; live broker submission remains locked.
