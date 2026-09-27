"""Deterministic Upstox sandbox rate-limit evidence capture.

This module classifies already-observed provider responses. It performs no
network I/O and does not authorize retries or orders.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from execution.provider_evidence import (
    ProviderEvidenceObservation,
    ProviderEvidenceState,
)
from execution.upstox_certification import (
    UpstoxFailureClass,
    classify_upstox_error,
)


@dataclass(frozen=True, slots=True)
class SandboxRateLimitEvidence:
    observation: ProviderEvidenceObservation
    http_status: int | None
    retry_after_seconds: float | None


def _parse_retry_after(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("retry-after value must be numeric") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError("retry-after value must be finite and non-negative")
    return parsed


def bounded_rate_limit_backoff(
    *,
    attempt: int,
    base_seconds: float = 1.0,
    cap_seconds: float = 30.0,
) -> float:
    """Return a deterministic bounded backoff value for a rate-limit retry.

    This is a policy primitive only; it does not perform a retry.
    """
    if attempt < 0:
        raise ValueError("attempt must be non-negative")
    if not math.isfinite(base_seconds) or base_seconds <= 0:
        raise ValueError("base_seconds must be finite and positive")
    if not math.isfinite(cap_seconds) or cap_seconds <= 0:
        raise ValueError("cap_seconds must be finite and positive")
    if base_seconds > cap_seconds:
        raise ValueError("base_seconds must not exceed cap_seconds")

    return min(cap_seconds, base_seconds * (2.0**attempt))


def capture_sandbox_rate_limit_evidence(
    *,
    response: Mapping[str, Any],
    retry_after_seconds: Any = None,
) -> SandboxRateLimitEvidence:
    """Classify an already-observed provider response without network I/O."""
    status_raw = response.get("status_code", response.get("http_status"))
    if status_raw is None:
        http_status = None
    else:
        try:
            http_status = int(status_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("provider HTTP status must be numeric") from exc

    code = str(response.get("code") or response.get("error_code") or "").strip()
    message = str(response.get("message") or "").strip()
    headers = response.get("headers")
    if headers is not None and not isinstance(headers, Mapping):
        raise ValueError("provider headers must be an object")

    header_retry_after = None
    if isinstance(headers, Mapping):
        header_retry_after = headers.get("Retry-After", headers.get("retry-after"))

    retry_after = _parse_retry_after(
        retry_after_seconds if retry_after_seconds is not None else header_retry_after
    )

    classified = classify_upstox_error(
        http_status=http_status,
        code=code,
        message=message,
    )

    if classified.failure_class is UpstoxFailureClass.RATE_LIMIT:
        state = ProviderEvidenceState.VERIFIED
        detail = "provider returned an explicit HTTP 429 rate-limit response"
    else:
        state = ProviderEvidenceState.UNVERIFIED
        detail = (
            f"provider response was classified as "
            f"{classified.failure_class.value}; rate limiting was not established"
        )

    return SandboxRateLimitEvidence(
        observation=ProviderEvidenceObservation(
            "rate_limit",
            "sandbox",
            "provider rate-limit response",
            state,
            detail,
        ),
        http_status=http_status,
        retry_after_seconds=retry_after,
    )


__all__ = [
    "SandboxRateLimitEvidence",
    "bounded_rate_limit_backoff",
    "capture_sandbox_rate_limit_evidence",
]
