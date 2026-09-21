"""Concrete point-in-time NSE Security Master history providers."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Sequence

from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)
from market.data.historical.nse_security_master_observation_history import (
    NSESecurityMasterObservationHistory,
)
from market.data.historical.security_lineage import (
    SecurityLineage,
    SecurityLineageObservation,
)
from market.data.historical.security_lineage_transition import (
    SecurityLineageTransition,
)
from market.data.historical.security_lineage_resolver import (
    resolve_security_lineage_transition_from_evidence,
)
from market.data.historical.nse_symbol_change import (
    NSESymbolChangeRecord,
)
from market.data.historical.symbol_history import (
    InstrumentSymbolInterval,
    InstrumentSymbolTimeline,
)
from market.data.historical.providers import (
    InstrumentSymbolHistoryProvider,
    SecurityLineageProvider,
)


class NSESecurityMasterHistoryProvider(InstrumentSymbolHistoryProvider):
    """Resolve symbol history from dated NSE Security Master observations.

    This provider intentionally requires explicit effective intervals.
    Snapshot presence alone is not converted into an economic effective date.
    """

    def __init__(
        self,
        histories: Iterable[NSESecurityMasterObservationHistory],
    ) -> None:
        materialized = tuple(histories)

        if not materialized:
            raise ValueError(
                "at least one Security Master observation history is required"
            )

        self._histories = materialized

    @property
    def histories(
        self,
    ) -> tuple[NSESecurityMasterObservationHistory, ...]:
        return self._histories

    def get_symbol_timeline(
        self,
        isin: str,
        exchange: str,
    ) -> InstrumentSymbolTimeline:
        if not isinstance(isin, str) or not isin.strip():
            raise ValueError("isin must be a non-empty string")

        if not isinstance(exchange, str) or not exchange.strip():
            raise ValueError("exchange must be a non-empty string")

        normalized_isin = isin.strip().upper()
        normalized_exchange = exchange.strip().upper()

        observations: list[NSESecurityMasterObservation] = []

        for history in self._histories:
            for observation in history.observations():
                if (
                    observation.isin == normalized_isin
                    and observation.exchange == normalized_exchange
                    and observation.series == "EQ"
                ):
                    observations.append(observation)

        if not observations:
            raise ValueError(
                "no Security Master observations found for "
                f"ISIN={normalized_isin}, exchange={normalized_exchange}"
            )

        by_date: dict[date, NSESecurityMasterObservation] = {}

        for observation in observations:
            previous = by_date.get(observation.observed_on)

            if previous is not None and previous != observation:
                raise ValueError(
                    "conflicting Security Master observations for "
                    f"ISIN={normalized_isin} on {observation.observed_on}"
                )

            by_date[observation.observed_on] = observation

        ordered = tuple(
            sorted(
                by_date.values(),
                key=lambda item: item.observed_on,
            )
        )

        # Observation history is evidence only. It does not establish
        # economic/legal effective dates, therefore a timeline cannot be
        # safely manufactured from snapshot presence alone.
        #
        # A stable symbol can safely be represented only when every observed
        # record has the same symbol and no transition is being inferred.

        symbols = {item.symbol for item in ordered}

        if len(symbols) != 1:
            raise ValueError(
                "multiple symbols found for ISIN; explicit symbol-change "
                "evidence is required before constructing a symbol timeline"
            )

        symbol = next(iter(symbols))

        return InstrumentSymbolTimeline(
            intervals=(
                InstrumentSymbolInterval(
                    isin=normalized_isin,
                    symbol=symbol,
                    exchange=normalized_exchange,
                    effective_from=ordered[0].observed_on,
                ),
            ),
        )


# =============================================================================
# 2. Concrete verified Security Lineage provider
# =============================================================================


class NSESecurityLineageProvider(SecurityLineageProvider):
    """Build verified security lineages from explicit NSE transitions.

    The provider requires:
      * explicit NSE symbol-change records;
      * dated Security Master evidence;
      * corroboration through the existing fail-closed resolver.

    No identity continuity is inferred.
    """

    def __init__(
        self,
        *,
        histories: Sequence[NSESecurityMasterObservationHistory],
        transitions: Sequence[NSESymbolChangeRecord],
    ) -> None:
        if not histories:
            raise ValueError(
                "at least one Security Master history is required"
            )

        self._histories = tuple(histories)
        self._transitions = tuple(transitions)

    @property
    def transitions(
        self,
    ) -> tuple[NSESymbolChangeRecord, ...]:
        return self._transitions

    def get_security_lineage(
        self,
        observation: SecurityLineageObservation,
    ) -> SecurityLineage:
        if not isinstance(observation, SecurityLineageObservation):
            raise TypeError(
                "observation must be a SecurityLineageObservation"
            )

        matching = tuple(
            transition
            for transition in self._transitions
            if (
                transition.old_symbol == observation.symbol
                or transition.new_symbol == observation.symbol
            )
        )

        # No transition for this symbol means the caller has supplied an
        # already-stable identity. It is safe to return the supplied
        # observation as a one-interval lineage.
        if not matching:
            return SecurityLineage(
                lineage_id=(
                    f"{observation.exchange}-"
                    f"{observation.isin}-"
                    f"{observation.fin_instrm_id}"
                ),
                observations=(observation,),
            )

        # Build the lineage only from explicit transition records.
        #
        # The existing resolver corroborates each transition against
        # Security Master observations and rejects contradictory evidence.
        all_evidence = tuple(
            evidence
            for history in self._histories
            for snapshot in history.snapshots
            for evidence in snapshot.evidence
        )

        resolved = []

        for record in matching:
            transition = SecurityLineageTransition.from_nse_symbol_change(
                record
            )

            result = resolve_security_lineage_transition_from_evidence(
                transition,
                all_evidence,
                series=observation.series,
                exchange=observation.exchange,
            )

            resolved.append(result)

        if not resolved:
            raise ValueError(
                "unable to establish Security Master lineage"
            )

        def _matches_identity(
            endpoint: SecurityLineageObservation,
        ) -> bool:
            return (
                endpoint.fin_instrm_id == observation.fin_instrm_id
                and endpoint.symbol == observation.symbol
                and endpoint.series == observation.series
                and endpoint.isin == observation.isin
                and endpoint.exchange == observation.exchange
            )

        relevant = [
            result
            for result in resolved
            if _matches_identity(result.before)
            or _matches_identity(result.after)
        ]

        if not relevant:
            raise ValueError(
                "explicit transition evidence does not exactly corroborate "
                "the requested security identity; continuity was not inferred"
            )

        # An explicit NSE transition date is sufficient to construct the
        # symbol intervals.  The dated Security Master observations provide
        # the concrete identity at each endpoint; the transition record
        # provides the boundary between them.
        #
        # No continuity is inferred from ISIN or FinInstrmId.  The endpoint
        # identities are retained exactly as corroborated by the evidence.

        lineage_observations: list[SecurityLineageObservation] = []

        for result in relevant:
            transition = result.transition

            before = SecurityLineageObservation(
                fin_instrm_id=result.before.fin_instrm_id,
                symbol=result.before.symbol,
                series=result.before.series,
                isin=result.before.isin,
                exchange=result.before.exchange,
                effective_from=result.before.observed_on,
                effective_to=transition.effective_date.fromordinal(
                    transition.effective_date.toordinal() - 1
                ),
                source=transition.source,
            )

            after = SecurityLineageObservation(
                fin_instrm_id=result.after.fin_instrm_id,
                symbol=result.after.symbol,
                series=result.after.series,
                isin=result.after.isin,
                exchange=result.after.exchange,
                effective_from=transition.effective_date,
                effective_to=None,
                source=transition.source,
            )

            lineage_observations.extend((before, after))

        unique_observations = {
            (
                item.fin_instrm_id,
                item.symbol,
                item.series,
                item.isin,
                item.exchange,
                item.effective_from,
                item.effective_to,
                item.source,
            ): item
            for item in lineage_observations
        }

        ordered = tuple(
            sorted(
                unique_observations.values(),
                key=lambda item: (
                    item.effective_from,
                    item.symbol,
                    item.fin_instrm_id,
                ),
            )
        )

        return SecurityLineage(
            lineage_id=(
                f"{observation.exchange}-"
                f"{observation.isin}-"
                f"{observation.fin_instrm_id}"
            ),
            observations=ordered,
        )
