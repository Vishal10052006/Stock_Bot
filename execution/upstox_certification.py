"""Upstox provider certification helpers.

These helpers classify provider failures without turning an error into a trading
decision. They are deliberately broker-neutral at the execution boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UpstoxFailureClass(str, Enum):
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT = "RATE_LIMIT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    NETWORK = "NETWORK"
    REJECTION = "REJECTION"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class UpstoxProviderError:
    failure_class: UpstoxFailureClass
    http_status: int | None
    code: str
    message: str
    retryable: bool
    requires_reconciliation: bool


def classify_upstox_error(
    *,
    http_status: int | None = None,
    code: str = "",
    message: str = "",
) -> UpstoxProviderError:
    """Classify an observed provider error fail-closed.

    A submission ambiguity is never classified as permission to retry. Network,
    timeout, and unknown outcomes require broker-state reconciliation first.
    """
    normalized = f"{code} {message}".strip().lower()
    if http_status == 401:
        kind = UpstoxFailureClass.AUTHENTICATION
        return UpstoxProviderError(kind, http_status, code, message, False, False)
    if http_status == 403:
        kind = UpstoxFailureClass.AUTHORIZATION
        return UpstoxProviderError(kind, http_status, code, message, False, False)
    if http_status == 404 or "not found" in normalized:
        kind = UpstoxFailureClass.NOT_FOUND
        return UpstoxProviderError(kind, http_status, code, message, False, True)
    if http_status == 429:
        kind = UpstoxFailureClass.RATE_LIMIT
        return UpstoxProviderError(kind, http_status, code, message, True, False)
    if http_status is not None and http_status >= 500:
        kind = UpstoxFailureClass.PROVIDER_UNAVAILABLE
        return UpstoxProviderError(kind, http_status, code, message, True, True)
    if any(token in normalized for token in ("timeout", "timed out", "connection", "network")):
        kind = UpstoxFailureClass.NETWORK
        return UpstoxProviderError(kind, http_status, code, message, False, True)
    if any(token in normalized for token in ("rejected", "reject", "udapi")):
        kind = UpstoxFailureClass.REJECTION
        return UpstoxProviderError(kind, http_status, code, message, False, False)
    if http_status == 400:
        kind = UpstoxFailureClass.VALIDATION
        return UpstoxProviderError(kind, http_status, code, message, False, False)
    return UpstoxProviderError(
        UpstoxFailureClass.UNKNOWN,
        http_status,
        code,
        message,
        False,
        True,
    )


def validate_rejection_state(*, status: str, reason: str) -> None:
    """Require an explicit broker rejection reason."""
    if status.strip().lower() != "rejected":
        raise ValueError("provider rejection certification requires rejected status")
    if not reason.strip():
        raise ValueError("provider rejection must preserve a non-empty reason")


def assert_unknown_requires_reconciliation(error: UpstoxProviderError) -> None:
    """Fail closed if an ambiguous provider failure lacks reconciliation."""
    if error.failure_class in {
        UpstoxFailureClass.NETWORK,
        UpstoxFailureClass.PROVIDER_UNAVAILABLE,
        UpstoxFailureClass.UNKNOWN,
    } and not error.requires_reconciliation:
        raise ValueError("ambiguous provider failure must require reconciliation")


__all__ = [
    "UpstoxFailureClass",
    "UpstoxProviderError",
    "classify_upstox_error",
    "validate_rejection_state",
    "assert_unknown_requires_reconciliation",
]
