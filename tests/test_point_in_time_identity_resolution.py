"""Tests for explicit PIT-to-provider instrument resolution."""

from datetime import date

import pytest

from market.data.historical.identity_resolution import (
    PointInTimeInstrumentResolver,
)
from market.data.historical.nse_security_master_evidence_snapshot import (
    NSESecurityMasterEvidenceSnapshot,
)
from market.data.historical.nse_security_master_observation_history import (
    NSESecurityMasterObservationHistory,
)
from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)
from market.data.historical.nse_symbol_change import (
    NSESymbolChangeRecord,
)
from market.data.historical.point_in_time_universe import (
    UniverseIdentityRecord,
)
from market.data.historical.security_lineage import (
    SecurityLineageObservation,
)
from market.data.historical.nse_security_master_history_provider import (
    NSESecurityLineageProvider,
)
from market.data.ingestion.providers.upstox.instrument_mapper import (
    UpstoxInstrumentMapper,
)


def make_observation(
    *,
    observed_on: date,
    symbol: str,
    isin: str,
    fin_instrm_id: str,
) -> NSESecurityMasterObservation:
    return NSESecurityMasterObservation(
        observed_on=observed_on,
        symbol=symbol,
        isin=isin,
        fin_instrm_id=fin_instrm_id,
        series="EQ",
        exchange="NSE",
    )


def make_snapshot(
    observation: NSESecurityMasterObservation,
) -> NSESecurityMasterEvidenceSnapshot:
    from market.data.historical.nse_security_master import (
        NSESecurityMasterRecord,
    )
    from market.data.historical.nse_security_master_evidence import (
        NSESecurityMasterEvidence,
    )
    from market.data.historical.nse_security_master_lifecycle import (
        NSESecurityMasterLifecycle,
    )

    identity = NSESecurityMasterRecord(
        snapshot_date=observation.observed_on,
        fin_instrm_id=observation.fin_instrm_id,
        symbol=observation.symbol,
        series=observation.series,
        isin=observation.isin,
        exchange=observation.exchange,
    )

    lifecycle = NSESecurityMasterLifecycle(
        listing_date=None,
        removal_date=None,
        readmission_date=None,
        normal_market_status="1",
        normal_market_eligibility="0",
        deletion_flag="N",
    )

    evidence = NSESecurityMasterEvidence(
        identity=identity,
        lifecycle=lifecycle,
    )

    return NSESecurityMasterEvidenceSnapshot(
        snapshot_date=observation.observed_on,
        evidence=(evidence,),
    )


def make_history(
    *observations: NSESecurityMasterObservation,
) -> NSESecurityMasterObservationHistory:
    return NSESecurityMasterObservationHistory(
        snapshots=tuple(
            make_snapshot(observation)
            for observation in observations
        )
    )


def make_pit_identity(
    *,
    symbol: str,
    isin: str,
    fin_instrm_id: str,
) -> UniverseIdentityRecord:
    return UniverseIdentityRecord(
        symbol=symbol,
        isin=isin,
        fin_instrm_id=fin_instrm_id,
        upstox_instrument_key=None,
    )


def make_lineage_provider() -> NSESecurityLineageProvider:
    old = make_observation(
        observed_on=date(2026, 6, 25),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )
    new = make_observation(
        observed_on=date(2026, 7, 2),
        symbol="NEWNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    transition = NSESymbolChangeRecord(
        company="Test Company",
        old_symbol="OLDNAME",
        new_symbol="NEWNAME",
        effective_date=date(2026, 7, 1),
        source="test",
    )

    return NSESecurityLineageProvider(
        histories=(make_history(old, new),),
        transitions=(transition,),
    )


def test_direct_current_mapping_resolves_without_lineage() -> None:
    mapper = UpstoxInstrumentMapper(
        {
            "RELIANCE": "NSE_EQ|INE002A01018",
        }
    )

    resolver = PointInTimeInstrumentResolver(
        instrument_mapper=mapper,
    )

    pit = make_pit_identity(
        symbol="RELIANCE",
        isin="INE002A01018",
        fin_instrm_id="500",
    )

    resolved = resolver.resolve(
        pit,
        as_of=date(2026, 9, 15),
    )

    assert resolved.provider_symbol == "RELIANCE"
    assert resolved.provider_instrument_key == "NSE_EQ|INE002A01018"


def test_renamed_symbol_requires_explicit_lineage() -> None:
    mapper = UpstoxInstrumentMapper(
        {
            "NEWNAME": "NSE_EQ|INE000A01000",
        }
    )

    resolver = PointInTimeInstrumentResolver(
        instrument_mapper=mapper,
    )

    pit = make_pit_identity(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    with pytest.raises(
        ValueError,
        match="no SecurityLineageProvider",
    ):
        resolver.resolve(
            pit,
            as_of=date(2026, 7, 2),
        )


def test_renamed_symbol_resolves_through_verified_lineage() -> None:
    mapper = UpstoxInstrumentMapper(
        {
            "NEWNAME": "NSE_EQ|INE000A01000",
        }
    )

    resolver = PointInTimeInstrumentResolver(
        instrument_mapper=mapper,
        lineage_provider=make_lineage_provider(),
    )

    pit = make_pit_identity(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    resolved = resolver.resolve(
        pit,
        as_of=date(2026, 7, 2),
    )

    assert resolved.pit_identity.symbol == "OLDNAME"
    assert resolved.provider_symbol == "NEWNAME"
    assert resolved.provider_instrument_key == (
        "NSE_EQ|INE000A01000"
    )


def test_matching_isin_without_provider_mapping_does_not_infer_continuity() -> None:
    mapper = UpstoxInstrumentMapper(
        {
            "OTHERNAME": "NSE_EQ|INE000A01000",
        }
    )

    resolver = PointInTimeInstrumentResolver(
        instrument_mapper=mapper,
    )

    pit = make_pit_identity(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    with pytest.raises(
        ValueError,
        match="no SecurityLineageProvider",
    ):
        resolver.resolve(
            pit,
            as_of=date(2026, 7, 2),
        )


def test_provider_isin_mismatch_fails_closed() -> None:
    mapper = UpstoxInstrumentMapper(
        {
            "RELIANCE": "NSE_EQ|INE999A99999",
        }
    )

    resolver = PointInTimeInstrumentResolver(
        instrument_mapper=mapper,
    )

    pit = make_pit_identity(
        symbol="RELIANCE",
        isin="INE002A01018",
        fin_instrm_id="500",
    )

    with pytest.raises(
        ValueError,
        match="ISIN mismatch",
    ):
        resolver.resolve(
            pit,
            as_of=date(2026, 9, 15),
        )
