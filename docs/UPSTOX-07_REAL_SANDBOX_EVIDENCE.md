# UPSTOX-07 — Real Sandbox Evidence

## Scope

This record captures empirical evidence from the Upstox Sandbox integration test and the provider capability boundary observed through the official Python SDK.

## Local regression evidence

Focused sandbox transport tests passed in the dedicated UPSTOX-07 worktree:

- `tests/execution/test_upstox_sandbox_client.py`
- `tests/execution/test_upstox_sdk_sandbox_cancel.py`
- Result: **8 passed, 1 deselected**

The deselected test is the real-provider integration case, which is intentionally excluded from the default pytest invocation.

## Real provider evidence

The real-provider integration test was explicitly enabled with the `integration` marker:

`pytest -q -m integration tests/execution/test_upstox_sandbox_client.py -k real_upstox_sandbox_order_lifecycle`

Result: **1 passed, 7 deselected**

This verifies the sandbox Place Order V3 → broker order ID → Cancel Order V3 acknowledgement boundary against the real Upstox sandbox.

The test does not claim final broker order state or position reconciliation because the installed SDK sandbox capability boundary does not provide the required order-history/position evidence used by the production reconciliation contract.

## Previously observed provider evidence

1. A sandbox-authenticated Place Order V3 request reached Upstox successfully.
2. An invalid instrument token produced the provider validation error `UDAPI100011`.
3. After using a valid instrument key, the order submission progressed to the broker response boundary.
4. The installed official SDK (`upstox-python-sdk 2.23.0`) rejects `/v2/order/history` locally when configured with `sandbox=True`, raising:
   `This API is not available in sandbox mode.`

## Provider capability boundary

Current Upstox documentation lists Place Order, Place Order V3, Modify Order, Modify Order V3, Cancel Order and Cancel Order V3 as Sandbox-enabled APIs.

The Upstox sandbox announcement describes comprehensive order lifecycle testing and historical records, while the installed SDK sandbox whitelist does not permit the `/v2/order/history` resource. The project therefore does not infer sandbox order-history support solely from documentation text.

## Certification status

- Sandbox authentication: **VERIFIED empirically**
- Place Order V3 reachability: **VERIFIED empirically**
- Invalid instrument rejection handling: **VERIFIED empirically**
- Place Order V3 → Cancel Order V3 API boundary: **VERIFIED empirically**
- Full place → history → cancel lifecycle: **NOT CERTIFIED** because the installed SDK blocks order history in sandbox mode
- Sandbox position reconciliation: **NOT CERTIFIED**
- Production reconciliation contract: **UNCHANGED**
- Live execution: **LOCKED**

## Required follow-up

Use a sandbox-supported status/reconciliation mechanism only after verifying the current provider/SDK capability. Do not weaken the production reconciliation contract to accommodate a sandbox limitation.
