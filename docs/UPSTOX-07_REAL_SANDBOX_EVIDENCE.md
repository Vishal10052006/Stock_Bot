# UPSTOX-07 — Real Sandbox Evidence

## Scope

This record captures empirical evidence from the Upstox Sandbox integration test and the provider capability boundary observed through the official Python SDK.

## Observed evidence

1. A sandbox-authenticated Place Order V3 request reached Upstox successfully.
2. An invalid instrument token produced the provider validation error `UDAPI100011`.
3. After using a valid instrument key, the order submission progressed to the broker response boundary.
4. The installed official SDK (`upstox-python-sdk 2.23.0`) rejects `/v2/order/history` locally when configured with `sandbox=True`, raising:
   `This API is not available in sandbox mode.`

## Provider capability boundary

Current Upstox documentation lists Place Order, Place Order V3, Modify Order, Modify Order V3, Cancel Order and Cancel Order V3 as Sandbox-enabled APIs.

The Upstox sandbox announcement describes comprehensive order lifecycle testing and historical records, while the current SDK sandbox whitelist does not permit the `/v2/order/history` resource. The project therefore does not infer sandbox order-history support solely from the SDK documentation text.

## Certification status

- Sandbox authentication: VERIFIED empirically.
- Place Order V3 reachability: VERIFIED empirically.
- Invalid instrument rejection handling: VERIFIED empirically.
- Full place → history → cancel lifecycle: NOT CERTIFIED because the installed SDK blocks order history in sandbox mode.
- Sandbox position reconciliation: NOT CERTIFIED.
- Live execution: LOCKED.

## Required follow-up

Use a sandbox-supported status/cancellation mechanism only after verifying the current provider/SDK capability. Do not weaken the production reconciliation contract to accommodate a sandbox limitation.
