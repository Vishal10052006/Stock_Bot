"""Runtime safety mode for M20 shadow operation."""

from __future__ import annotations

from dataclasses import dataclass
import os


class UnsafeRuntimeModeError(RuntimeError):
    """Raised when runtime configuration could permit live order submission."""


@dataclass(frozen=True, slots=True)
class RuntimeSafety:
    """Immutable runtime safety contract.

    M20 has exactly one supported operating mode: SHADOW. Live broker order
    submission is a hard-disabled capability, not an opt-in environment flag.
    """

    mode: str = "SHADOW"
    live_broker_order_submission: bool = False

    def __post_init__(self) -> None:
        """Reject every configuration that is not shadow-only."""
        if self.mode.strip().upper() != "SHADOW":
            raise UnsafeRuntimeModeError(
                "M20 runtime supports SHADOW mode only"
            )
        if self.live_broker_order_submission:
            raise UnsafeRuntimeModeError(
                "live broker order submission is hard-disabled in M20"
            )

    def assert_safe(self) -> None:
        """Fail closed if the immutable safety contract is violated."""
        if self.mode != "SHADOW" or self.live_broker_order_submission:
            raise UnsafeRuntimeModeError(
                "M20 safety contract violation"
            )


def load_runtime_safety() -> RuntimeSafety:
    """Load and validate the M20 safety posture from the environment."""
    mode = os.getenv("STOCK_BOT_MODE", "SHADOW").strip().upper()
    raw_live = os.getenv(
        "STOCK_BOT_LIVE_ORDER_SUBMISSION",
        "false",
    ).strip().lower()

    if raw_live in {"1", "true", "yes", "on"}:
        raise UnsafeRuntimeModeError(
            "STOCK_BOT_LIVE_ORDER_SUBMISSION is forbidden in M20"
        )

    if raw_live not in {"0", "false", "no", "off", ""}:
        raise UnsafeRuntimeModeError(
            "STOCK_BOT_LIVE_ORDER_SUBMISSION must be false when present"
        )

    return RuntimeSafety(
        mode=mode,
        live_broker_order_submission=False,
    )
