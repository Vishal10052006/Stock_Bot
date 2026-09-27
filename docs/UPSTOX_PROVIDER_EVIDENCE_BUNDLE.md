# Upstox Provider Evidence Bundle

## Purpose

Provide one canonical composition boundary from captured provider observations to the existing Upstox readiness attestation.

## Flow

```
Captured provider observations
        ↓
ProviderEvidenceReport("upstox")
        ↓
build_upstox_provider_evidence_bundle()
        ↓
UpstoxReadinessAttestation
        ↓
BLOCKED / VERIFIED
```

## Rules

- observations must already have been captured by an intentional provider-observation process;
- the bundle performs no network I/O;
- it does not submit, cancel, or retry orders;
- it does not perform broker reconciliation;
- it does not change Risk quantity;
- it does not authorize Execution;
- UNVERIFIED, BLOCKED, and FAILED observations remain blocking readiness;
- the existing deterministic readiness fingerprint remains authoritative for the resulting attestation.

## Evidence boundary

Software evidence helpers remain distinct from real provider evidence. A helper can classify an observed response, but no provider capability becomes VERIFIED merely because the helper exists.

If required provider observations are absent, the resulting readiness remains BLOCKED.

## Safety

Live broker execution remains locked independently of this bundle and independently of readiness status.
