"""Explicit point-in-time to provider instrument identity resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from market.data.historical.point_in_time_universe import (
    UniverseIdentityRecord,
)
from market.data.historical.security_lineage import (
    SecurityLineageObservation,
)
from market.data.historical.providers import SecurityLineageProvider
from market.data.ingestion.providers.upstox.instrument_mapper import (
    UpstoxInstrumentMapper,
)


@dataclass(frozen=True, slots=True)
class ResolvedHistoricalInstrument:
    """Resolved PIT identity plus the exact current provider identity."""

    pit_identity: UniverseIdentityRecord
    provider_symbol: str
    provider_instrument_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.pit_identity, UniverseIdentityRecord):
            raise TypeError(
                "pit_identity must be a UniverseIdentityRecord"
            )

        for name, value in (
            ("provider_symbol", self.provider_symbol),
            ("provider_instrument_key", self.provider_instrument_key),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{name} must be a non-empty string"
                )

        object.__setattr__(
            self,
            "provider_symbol",
            self.provider_symbol.strip().upper(),
        )
        object.__setattr__(
            self,
            "provider_instrument_key",
            self.provider_instrument_key.strip(),
        )


class PointInTimeInstrumentResolver:
    """Resolve a PIT universe identity to a provider instrument.

    Resolution policy is deliberately fail-closed:

    1. A direct current-symbol mapping is accepted.
    2. If the PIT symbol is not currently mapped, explicit verified
       SecurityLineage evidence is required.
    3. The provider symbol must be the explicitly corroborated post-transition
       symbol.
    4. The provider instrument key must be obtained from the provider mapper.
    5. No continuity is inferred from ISIN or FinInstrmId alone.
    """

    def __init__(
        self,
        *,
        instrument_mapper: UpstoxInstrumentMapper,
        lineage_provider: SecurityLineageProvider | None = None,
    ) -> None:
        if not isinstance(
            instrument_mapper,
            UpstoxInstrumentMapper,
        ):
            raise TypeError(
                "instrument_mapper must be an UpstoxInstrumentMapper"
            )

        if lineage_provider is not None and not isinstance(
            lineage_provider,
            SecurityLineageProvider,
        ):
            raise TypeError(
                "lineage_provider must implement SecurityLineageProvider"
            )

        self._instrument_mapper = instrument_mapper
        self._lineage_provider = lineage_provider

    @property
    def instrument_mapper(self) -> UpstoxInstrumentMapper:
        return self._instrument_mapper

    @property
    def lineage_provider(self) -> SecurityLineageProvider | None:
        return self._lineage_provider

    def resolve(
        self,
        pit_identity: UniverseIdentityRecord,
        *,
        as_of: date,
    ) -> ResolvedHistoricalInstrument:
        if not isinstance(
            pit_identity,
            UniverseIdentityRecord,
        ):
            raise TypeError(
                "pit_identity must be a UniverseIdentityRecord"
            )

        if not isinstance(as_of, date):
            raise TypeError("as_of must be a date")

        pit_symbol = pit_identity.symbol.strip().upper()

        # ---------------------------------------------------------------
        # Path 1: direct current provider mapping.
        # ---------------------------------------------------------------
        try:
            provider_identity = self._instrument_mapper.identity(
                pit_symbol
            )
        except KeyError:
            provider_identity = None

        if provider_identity is not None:
            if provider_identity.isin != pit_identity.isin:
                raise ValueError(
                    "direct provider mapping has an ISIN mismatch with "
                    "the PIT identity; continuity was not inferred"
                )

            return ResolvedHistoricalInstrument(
                pit_identity=pit_identity,
                provider_symbol=provider_identity.symbol,
                provider_instrument_key=provider_identity.instrument_key,
            )

        # ---------------------------------------------------------------
        # Path 2: renamed historical symbol.
        # Explicit lineage is mandatory.
        # ---------------------------------------------------------------
        if self._lineage_provider is None:
            raise ValueError(
                "PIT symbol is not directly mapped by the provider and "
                "no SecurityLineageProvider was supplied; "
                "historical identity resolution failed closed"
            )

        observation = SecurityLineageObservation(
            effective_from=as_of,
            fin_instrm_id=pit_identity.fin_instrm_id,
            symbol=pit_symbol,
            series="EQ",
            isin=pit_identity.isin,
            exchange="NSE",
            source="pit_universe",
        )

        lineage = self._lineage_provider.get_security_lineage(
            observation
        )

        resolved_observation = lineage.observation_on(as_of)

        if resolved_observation is None:
            raise ValueError(
                "verified SecurityLineage contains no observation applicable "
                f"on PIT date {as_of}"
            )

        provider_symbol = resolved_observation.symbol

        try:
            provider_identity = self._instrument_mapper.identity(
                provider_symbol
            )
        except KeyError as exc:
            raise ValueError(
                "verified historical lineage resolves to provider symbol "
                f"{provider_symbol}, but the current provider has no "
                "instrument mapping for that symbol"
            ) from exc

        # The current provider identity must independently corroborate the
        # explicit lineage endpoint. This is NOT continuity inference:
        # lineage selected the symbol; provider mapping supplies the current
        # provider instrument key.
        if provider_identity.isin != resolved_observation.isin:
            raise ValueError(
                "provider identity does not match the verified lineage "
                "endpoint ISIN; resolution failed closed"
            )

        return ResolvedHistoricalInstrument(
            pit_identity=pit_identity,
            provider_symbol=provider_symbol,
            provider_instrument_key=provider_identity.instrument_key,
        )
