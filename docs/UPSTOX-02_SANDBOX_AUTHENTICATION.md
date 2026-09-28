# UPSTOX-02 — Sandbox Authentication Validation

## Scope

UPSTOX-02 validates the credential/transport boundary for the official Upstox Python SDK in **sandbox mode**.

This phase does **not** enable live trading and does **not** place an order.

## Implemented boundary

`execution/adapters/upstox_sdk.py` constructs:

`Configuration(sandbox=True)`

and injects the caller-supplied sandbox access token.

Credential acquisition remains outside the execution domain. The SDK client does not read `.env`, environment variables, or files itself.

## Automated certification

The existing unit tests verify:

- sandbox mode is forced;
- the supplied token is attached to the SDK configuration;
- SDK construction errors cross the `UpstoxSDKError` boundary;
- provider errors are normalized;
- empty credentials are rejected;
- position queries remain explicitly unsupported in the sandbox client.

An additional opt-in integration test validates a real sandbox token using a **read-only order-history lookup**. It never places, modifies, or cancels an order.

Required environment:

- `UPSTOX_SANDBOX_ACCESS_TOKEN`
- `UPSTOX_SANDBOX_AUTH_CONFIRM=YES`

The token must never be committed to the repository or pasted into chat.

## Safety

UPSTOX live execution remains disabled.

Authentication success alone does **not** authorize order submission or live execution.

## Exit criteria

UPSTOX-02 is provider-certified only after the opt-in authentication test succeeds against the current Upstox sandbox.

Next phase:

**UPSTOX-03 — Real Sandbox Order Lifecycle Validation**
