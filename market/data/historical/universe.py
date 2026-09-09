"""Point-in-time historical instrument-universe contracts.

The universe layer defines which instruments are eligible for research at a
given point in time. It must not select instruments retrospectively using
future information.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class UniverseMembership:
    """One point-in-time interval during which an instrument is eligible."""

    symbol: str
    exchange: str
    effective_from: date
    effective_to: date | None = None

    def __post_init__(self) -> None:
        """Validate the membership interval."""
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")

        if not self.exchange.strip():
            raise ValueError("exchange must not be empty")

        if not isinstance(self.effective_from, date):
            raise TypeError("effective_from must be a date")

        if isinstance(self.effective_from, __import__("datetime").datetime):
            raise TypeError("effective_from must be a date")

        if self.effective_to is not None:
            if not isinstance(self.effective_to, date):
                raise TypeError("effective_to must be a date")

            if isinstance(self.effective_to, __import__("datetime").datetime):
                raise TypeError("effective_to must be a date")

            if self.effective_to < self.effective_from:
                raise ValueError(
                    "effective_to must be greater than or equal to "
                    "effective_from"
                )

        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "exchange", self.exchange.strip().upper())


@dataclass(frozen=True, slots=True)
class UniverseSnapshot:
    """Immutable point-in-time universe selection."""

    as_of: date
    policy_version: str
    symbols: tuple[str, ...]
    source: str

    def __post_init__(self) -> None:
        """Validate and canonicalize the snapshot."""
        if not isinstance(self.as_of, date):
            raise TypeError("as_of must be a date")

        if isinstance(self.as_of, __import__("datetime").datetime):
            raise TypeError("as_of must be a date")

        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty")

        if not self.source.strip():
            raise ValueError("source must not be empty")

        normalized = tuple(
            symbol.strip().upper()
            for symbol in self.symbols
        )

        if any(not symbol for symbol in normalized):
            raise ValueError("symbols must not contain empty values")

        if len(normalized) != len(set(normalized)):
            raise ValueError("symbols must not contain duplicates")

        if normalized != tuple(sorted(normalized)):
            raise ValueError("symbols must be sorted")

        object.__setattr__(
            self,
            "policy_version",
            self.policy_version.strip(),
        )
        object.__setattr__(self, "source", self.source.strip())
        object.__setattr__(self, "symbols", normalized)

    def contains(self, symbol: str) -> bool:
        """Return whether the snapshot contains an instrument."""
        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string")

        return symbol.strip().upper() in self.symbols


@dataclass(frozen=True, slots=True)
class UniversePolicy:
    """Versioned identity for a universe-selection policy.

    Selection criteria are intentionally not encoded here yet. The frozen
    trading specification requires deterministic and versioned selection,
    while the numerical liquidity threshold remains a separate policy
    decision.
    """

    version: str
    name: str

    def __post_init__(self) -> None:
        """Validate the policy identity."""
        if not self.version.strip():
            raise ValueError("version must not be empty")

        if not self.name.strip():
            raise ValueError("name must not be empty")

        object.__setattr__(self, "version", self.version.strip())
        object.__setattr__(self, "name", self.name.strip())


@dataclass(frozen=True, slots=True)
class UniverseMembershipTimeline:
    """Chronological, non-overlapping universe membership intervals."""

    memberships: tuple[UniverseMembership, ...]

    def __post_init__(self) -> None:
        """Validate membership ordering and interval integrity."""
        if not self.memberships:
            raise ValueError(
                "memberships must not be empty"
            )

        if any(
            not isinstance(membership, UniverseMembership)
            for membership in self.memberships
        ):
            raise TypeError(
                "memberships must contain only UniverseMembership values"
            )

        grouped: dict[tuple[str, str], list[UniverseMembership]] = {}

        for membership in self.memberships:
            key = (
                membership.symbol,
                membership.exchange,
            )
            grouped.setdefault(key, []).append(membership)

        for key, values in grouped.items():
            ordered = tuple(
                sorted(
                    values,
                    key=lambda membership: membership.effective_from,
                )
            )

            if ordered != tuple(
                membership
                for membership in self.memberships
                if (
                    membership.symbol,
                    membership.exchange,
                ) == key
            ):
                raise ValueError(
                    "memberships must be chronological per instrument"
                )

            for previous, current in zip(
                ordered,
                ordered[1:],
            ):
                if previous.effective_to is None:
                    raise ValueError(
                        "open-ended membership must be the final "
                        "interval for an instrument"
                    )

                if current.effective_from <= previous.effective_to:
                    raise ValueError(
                        "universe membership intervals must not overlap"
                    )

    def is_member(
        self,
        *,
        symbol: str,
        exchange: str,
        as_of: date,
    ) -> bool:
        """Return whether an instrument is a member at ``as_of``."""
        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string")

        if not isinstance(exchange, str):
            raise TypeError("exchange must be a string")

        if not isinstance(as_of, date):
            raise TypeError("as_of must be a date")

        if isinstance(as_of, __import__("datetime").datetime):
            raise TypeError("as_of must be a date")

        normalized_symbol = symbol.strip().upper()
        normalized_exchange = exchange.strip().upper()

        for membership in self.memberships:
            if (
                membership.symbol != normalized_symbol
                or membership.exchange != normalized_exchange
            ):
                continue

            if as_of < membership.effective_from:
                continue

            if (
                membership.effective_to is None
                or as_of <= membership.effective_to
            ):
                return True

        return False


def build_universe_snapshot(
    candidates: tuple[str, ...],
    *,
    exchange: str,
    as_of: date,
    policy: UniversePolicy,
    liquidity_measurements: dict[str, "LiquidityMeasurement"],
    liquidity_policy: "LiquidityPolicy",
    instrument_status: dict[
        str,
        "InstrumentStatusTimeline",
    ] | None = None,
    source: str,
) -> UniverseSnapshot:
    """Build a deterministic point-in-time universe snapshot.

    Each candidate must satisfy all applicable point-in-time eligibility
    conditions:

    1. a liquidity measurement exists for ``as_of``;
    2. the measurement satisfies the configured liquidity policy;
    3. the instrument is active at ``as_of`` when lifecycle information
       is supplied.

    No current-day or future information is used by this selector.
    """
    from market.data.historical.instrument_status import (
        InstrumentStatusTimeline,
        InstrumentStatusType,
    )
    from market.data.historical.liquidity import (
        LiquidityMeasurement,
        LiquidityPolicy,
        is_liquid,
    )

    if not isinstance(candidates, tuple):
        raise TypeError("candidates must be a tuple")

    if not isinstance(exchange, str):
        raise TypeError("exchange must be a string")

    if isinstance(as_of, __import__("datetime").datetime):
        raise TypeError("as_of must be a date")

    if not isinstance(as_of, date):
        raise TypeError("as_of must be a date")

    if not isinstance(policy, UniversePolicy):
        raise TypeError("policy must be a UniversePolicy")

    if not isinstance(liquidity_policy, LiquidityPolicy):
        raise TypeError(
            "liquidity_policy must be a LiquidityPolicy"
        )

    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must not be empty")

    normalized_exchange = exchange.strip().upper()

    if not normalized_exchange:
        raise ValueError("exchange must not be empty")

    normalized_candidates = tuple(
        symbol.strip().upper()
        for symbol in candidates
    )

    if any(not symbol for symbol in normalized_candidates):
        raise ValueError(
            "candidates must not contain empty symbols"
        )

    if len(normalized_candidates) != len(set(normalized_candidates)):
        raise ValueError(
            "candidates must not contain duplicates"
        )

    normalized_measurements: dict[
        str,
        LiquidityMeasurement,
    ] = {}

    for symbol, measurement in liquidity_measurements.items():
        if not isinstance(symbol, str):
            raise TypeError(
                "liquidity_measurements keys must be strings"
            )

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError(
                "liquidity_measurements keys must not be empty"
            )

        if not isinstance(measurement, LiquidityMeasurement):
            raise TypeError(
                "liquidity_measurements values must be "
                "LiquidityMeasurement values"
            )

        if measurement.as_of != as_of:
            raise ValueError(
                "liquidity measurement as_of must match "
                "universe snapshot as_of"
            )

        normalized_measurements[normalized_symbol] = measurement

    normalized_status: dict[
        str,
        InstrumentStatusTimeline,
    ] = {}

    if instrument_status is not None:
        for symbol, timeline in instrument_status.items():
            if not isinstance(symbol, str):
                raise TypeError(
                    "instrument_status keys must be strings"
                )

            normalized_symbol = symbol.strip().upper()

            if not normalized_symbol:
                raise ValueError(
                    "instrument_status keys must not be empty"
                )

            if not isinstance(timeline, InstrumentStatusTimeline):
                raise TypeError(
                    "instrument_status values must be "
                    "InstrumentStatusTimeline values"
                )

            normalized_status[normalized_symbol] = timeline

    selected: list[str] = []

    for symbol in normalized_candidates:
        measurement = normalized_measurements.get(symbol)

        if measurement is None:
            continue

        timeline = normalized_status.get(symbol)

        if timeline is not None:
            status = timeline.status_on(as_of)

            if (
                status is not None
                and status != InstrumentStatusType.ACTIVE
            ):
                continue

        if is_liquid(
            measurement,
            liquidity_policy,
        ):
            selected.append(symbol)

    return UniverseSnapshot(
        as_of=as_of,
        policy_version=policy.version,
        symbols=tuple(sorted(selected)),
        source=source.strip(),
    )
