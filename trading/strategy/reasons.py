from __future__ import annotations

from collections.abc import Iterable

from .models import NoTradeReason


def deduplicate_reasons(reasons: Iterable[NoTradeReason]) -> tuple[NoTradeReason, ...]:
    """Preserve order while removing duplicate reasons."""
    seen: set[NoTradeReason] = set()
    result: list[NoTradeReason] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            result.append(reason)
    return tuple(result)


def primary_no_trade_reason(*reasons: NoTradeReason) -> NoTradeReason:
    """Choose the first explicit reason and fail closed when empty."""
    return reasons[0] if reasons else NoTradeReason.STRATEGY_CONDITION_FAILED
