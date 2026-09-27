# UPSTOX-18 — Provider Evidence Consolidation

## Purpose

Consolidate captured Upstox provider observations into the existing readiness attestation without creating a new authorization path.

## Implementation

build_upstox_readiness_from_provider_report() converts the canonical ProviderEvidenceReport into the existing UpstoxReadinessAttestation.

Rules:

- only a provider report for upstox is accepted;
- every provider observation is preserved as capability, environment, state, and detail;
- UNVERIFIED, BLOCKED, and FAILED capabilities keep the attestation blocked;
- an attestation is verified only when it contains at least one capability and every capability is VERIFIED;
- the existing deterministic evidence fingerprint remains the attestation identity;
- no network I/O occurs;
- no order is submitted or cancelled;
- no risk quantity or execution authorization is changed.

## Current provider status

The controlled Upstox evidence plan remains provider-observation driven. Software-level evidence helpers do not become real provider evidence automatically.

Current provider observations therefore remain UNVERIFIED until intentionally captured from the provider.

## Safety

This module is observational only. It does not authorize live execution.

Live broker execution remains locked until independent provider-readiness and governance gates are satisfied.
