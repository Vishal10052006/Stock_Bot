        OrderStatus.VALIDATED: {OrderStatus.SUBMITTING, OrderStatus.REJECTED_LOCAL},
        # Synchronous adapters may return a terminal or partial fill directly.
        # Do not invent an intermediate SUBMITTED/OPEN event when none occurred.
        OrderStatus.SUBMITTING: {
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.REJECTED_BROKER,
            OrderStatus.FAILED,
            OrderStatus.UNKNOWN,
        },
        OrderStatus.SUBMITTED: {
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.REJECTED_BROKER,
            OrderStatus.UNKNOWN,
        },
        OrderStatus.OPEN: {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.UNKNOWN,
        },
        OrderStatus.PARTIALLY_FILLED: {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.UNKNOWN,
        },
        # Broker refresh can lose visibility even after a terminal response.
        # UNKNOWN represents loss of authoritative broker state, not a new
        # business outcome, so terminal broker states must be recoverable to it.
        OrderStatus.FILLED: {OrderStatus.UNKNOWN},
        OrderStatus.CANCEL_PENDING: {OrderStatus.CANCELLED, OrderStatus.FILLED, OrderStatus.UNKNOWN},
        OrderStatus.CANCELLED: {OrderStatus.UNKNOWN},
        OrderStatus.EXPIRED: {OrderStatus.UNKNOWN},
        OrderStatus.REJECTED_BROKER: {OrderStatus.UNKNOWN},
        OrderStatus.FAILED: {OrderStatus.UNKNOWN},
        OrderStatus.UNKNOWN: {
            OrderStatus.SUBMITTED,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED_BROKER,
            OrderStatus.FAILED,
        },
    }

    @classmethod
    def transition(cls, current: OrderStatus, target: OrderStatus) -> OrderStatus:
        if target not in cls._ALLOWED.get(current, set()):
            raise ValueError(f"invalid order transition: {current.value} -> {target.value}")
        return target


class ExecutionEngine:
    """Execute risk-approved orders through a broker-neutral adapter."""
