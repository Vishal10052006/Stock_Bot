"""Deterministic resolver for corroborated security-lineage transitions."""

from __future__ import annotations

from collections.abc import Iterable

from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)
from market.data.historical.security_lineage_resolution import (
    SecurityLineageResolution,
)
from market.data.historical.security_lineage_transition import (
    SecurityLineageTransition,
)


class SecurityLineageResolutionError(ValueError):
    """Base error for security-lineage resolution failures."""


class SecurityLineageInsufficientEvidenceError(
    SecurityLineageResolutionError
):
    """Raised when available evidence is insufficient to resolve a transition."""


class SecurityLineageContradictoryEvidenceError(
    SecurityLineageResolutionError
):
    """Raised when evidence contradicts the proposed transition."""


class SecurityLineageAmbiguousEvidenceError(
    SecurityLineageResolutionError
):
    """Raised when evidence permits multiple valid observations."""



def resolve_security_lineage_transition_from_evidence(
    transition: SecurityLineageTransition,
    evidence: Iterable["NSESecurityMasterEvidence"],
    *,
    series: str = "EQ",
    exchange: str = "NSE",
) -> SecurityLineageResolution:
    """Resolve a symbol transition using identity + NSE lifecycle evidence.

    A retained old-symbol Security Master record may remain present after
    a symbol transition.  It is excluded from contradiction checks only when
    NSE explicitly marks that record as deleted.

    Lifecycle state is never inferred from absence.
    """

    from market.data.historical.nse_security_master_evidence import (
        NSESecurityMasterEvidence,
    )

    if not isinstance(transition, SecurityLineageTransition):
        raise TypeError(
            "transition must be a SecurityLineageTransition"
        )

    if not isinstance(series, str) or not series.strip():
        raise ValueError("series must be a non-empty string")

    if not isinstance(exchange, str) or not exchange.strip():
        raise ValueError("exchange must be a non-empty string")

    materialized = tuple(evidence)

    for index, item in enumerate(materialized):
        if not isinstance(item, NSESecurityMasterEvidence):
            raise TypeError(
                f"evidence[{index}] must be an "
                "NSESecurityMasterEvidence"
            )

    normalized_series = series.strip().upper()
    normalized_exchange = exchange.strip().upper()

    observations: list[NSESecurityMasterObservation] = []

    for item in materialized:
        identity = item.identity
        lifecycle = item.lifecycle

        if (
            identity.series != normalized_series
            or identity.exchange != normalized_exchange
        ):
            continue

        is_old_symbol = (
            identity.symbol == transition.old_symbol
        )

        is_post_transition = (
            identity.snapshot_date >= transition.effective_date
        )

        is_explicitly_deleted = (
            lifecycle.deletion_flag.strip().upper() == "Y"
        )

        if (
            is_old_symbol
            and is_post_transition
            and is_explicitly_deleted
        ):
            # NSE may retain a historical instrument record after deletion.
            # Explicit deletion means this is not evidence that the old
            # symbol remained active after the transition.
            continue

        observations.append(
            NSESecurityMasterObservation.from_record(identity)
        )

    old_post_transition = tuple(
        observation
        for observation in observations
        if (
            observation.symbol == transition.old_symbol
            and observation.observed_on >= transition.effective_date
        )
    )

    if old_post_transition:
        raise SecurityLineageContradictoryEvidenceError(
            "active old-symbol observation exists on or after transition"
        )

    return resolve_security_lineage_transition(
        transition,
        tuple(observations),
        series=normalized_series,
        exchange=normalized_exchange,
    )


def resolve_security_lineage_transition(
    transition: SecurityLineageTransition,
    observations: Iterable[NSESecurityMasterObservation],
    *,
    series: str = "EQ",
    exchange: str = "NSE",
) -> SecurityLineageResolution:
    """Resolve one transition against dated Security Master observations.

    Resolution is deliberately conservative:

    * the old symbol must be observed before the transition date;
    * the new symbol must be observed on or after the transition date;
    * the selected observations must be unique on their observation dates;
    * contradictory symbol observations around the transition are rejected;
    * ISIN and FinInstrmId continuity is never inferred.
    """

    if not isinstance(
        transition,
        SecurityLineageTransition,
    ):
        raise TypeError(
            "transition must be a SecurityLineageTransition"
        )

    if not isinstance(series, str) or not series.strip():
        raise ValueError("series must be a non-empty string")

    if not isinstance(exchange, str) or not exchange.strip():
        raise ValueError("exchange must be a non-empty string")

    normalized_series = series.strip().upper()
    normalized_exchange = exchange.strip().upper()

    materialized = tuple(observations)

    for index, observation in enumerate(materialized):
        if not isinstance(
            observation,
            NSESecurityMasterObservation,
        ):
            raise TypeError(
                f"observations[{index}] must be an "
                "NSESecurityMasterObservation"
            )

    scoped = tuple(
        observation
        for observation in materialized
        if (
            observation.series == normalized_series
            and observation.exchange == normalized_exchange
        )
    )

    if not scoped:
        raise SecurityLineageInsufficientEvidenceError(
            "no Security Master observations match the requested "
            "series and exchange"
        )

    old_observations = tuple(
        observation
        for observation in scoped
        if observation.symbol == transition.old_symbol
    )

    new_observations = tuple(
        observation
        for observation in scoped
        if observation.symbol == transition.new_symbol
    )

    before_candidates = tuple(
        observation
        for observation in old_observations
        if observation.observed_on < transition.effective_date
    )

    after_candidates = tuple(
        observation
        for observation in new_observations
        if observation.observed_on >= transition.effective_date
    )

    if not before_candidates:
        raise SecurityLineageInsufficientEvidenceError(
            "no old-symbol observation exists before transition"
        )

    if not after_candidates:
        raise SecurityLineageInsufficientEvidenceError(
            "no new-symbol observation exists on or after transition"
        )

    contradictory_before = tuple(
        observation
        for observation in new_observations
        if observation.observed_on < transition.effective_date
    )

    if contradictory_before:
        raise SecurityLineageContradictoryEvidenceError(
            "new-symbol observation exists before transition"
        )

    contradictory_after = tuple(
        observation
        for observation in old_observations
        if observation.observed_on >= transition.effective_date
    )

    if contradictory_after:
        raise SecurityLineageContradictoryEvidenceError(
            "old-symbol observation exists on or after transition"
        )

    latest_before_date = max(
        observation.observed_on
        for observation in before_candidates
    )

    earliest_after_date = min(
        observation.observed_on
        for observation in after_candidates
    )

    before_at_date = tuple(
        observation
        for observation in before_candidates
        if observation.observed_on == latest_before_date
    )

    after_at_date = tuple(
        observation
        for observation in after_candidates
        if observation.observed_on == earliest_after_date
    )

    if len(before_at_date) != 1:
        raise SecurityLineageAmbiguousEvidenceError(
            "multiple old-symbol observations exist on the selected "
            "pre-transition date"
        )

    if len(after_at_date) != 1:
        raise SecurityLineageAmbiguousEvidenceError(
            "multiple new-symbol observations exist on the selected "
            "post-transition date"
        )

    return SecurityLineageResolution(
        transition=transition,
        before=before_at_date[0],
        after=after_at_date[0],
    )
