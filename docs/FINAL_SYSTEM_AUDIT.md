| Current broker/exchange verification | **External evidence required** |
| Current regulatory verification | **External evidence required** |
| Strategy profitability | **Not established by architecture/tests** |
| Robust unseen-market performance | **Requires measured OOS/walk-forward evidence** |
| Paper-trading sufficiency | **Requires actual observations** |
| Controlled live deployment | **Not authorized** |

## 15. Non-negotiable conclusion

The correct state of STOCK BOT is:

**Research/Paper architecture: structurally mature and CI-verified.**

**Live trading: locked.**

**Profitability/robustness: not claimed without measured evidence.**

The next engineering work should be driven by actual research and paper-trading evidence rather than by artificially completing phase numbers.


## 16. Final hardening completed after Phase 27

The remaining software-side deployment gaps identified during final audit were closed without enabling live execution:

- deterministic provider-neutral instrument identity and resolver contract;
- Upstox sandbox adapter now requires explicit instrument resolution rather than treating a trading symbol as an instrument token;
- integer and instrument lot-size validation at the provider boundary;
- broker-order identity retention for refresh/cancel;
- restart-safe Upstox order recovery through provider Order History tag lookup when the injected client supports it;
- strict provider numeric validation and instrument tick-size validation;
- explicit rejection of multi-child/sliced broker responses until the canonical execution contract supports aggregation;
- fail-closed refresh when broker order identity or restart reconciliation is unavailable;
- Phase 26 controlled-deployment governance remains permanently blocked by the separate live lock, even when supplied checklist evidence is complete.

The remaining work is evidence acquisition, not permission to bypass the lock.

## 17. Consolidated remaining-gate runner — 2026-10-03

The repository now contains `scripts/final_readiness_local_gate.py`, a single
fail-closed operator command that evaluates the remaining locally actionable
paper, monitoring, and Module-10 readiness evidence without fabricating missing
observations or enabling live execution.

Run from the repository root:

```bash
python3 scripts/final_readiness_local_gate.py
```

The command validates the current readiness audit, uses the latest persisted
virtual-paper session when one exists, runs the CERT-08 soak validator and M-24
monitoring validator, and reports the exact CERT-12 provider evidence still
requiring intentional external observation.

The runner always reports the live execution path as LOCKED. It does not submit
orders, enable a broker adapter, or convert missing evidence into PASS.