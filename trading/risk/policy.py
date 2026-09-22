"""Risk-policy helpers.

The policy is explicit, versioned, and independent from trading code.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

from .contracts import RiskPolicy


def policy_fingerprint(policy: RiskPolicy) -> str:
    """Return a stable fingerprint for the exact policy contents."""
    payload = json.dumps(asdict(policy), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
