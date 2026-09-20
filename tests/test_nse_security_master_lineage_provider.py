from datetime import date

import pytest

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_evidence import (
    NSESecurityMasterEvidence,
)
from market.data.historical.nse_security_master_evidence_snapshot import (
    NSESecurityMasterEvidenceSnapshot,
)
from market.data.historical.nse_security_master_lifecycle import (
    NSESecurityMasterLifecycle,
)
from market.data.historical.nse_security_master_observation_history import (
    NSESecurityMasterObservationHistory,
)
from market.data.historical.nse_security_master_history_provider import (
    NSESecurityMasterHistoryProvider,
    NSESecurityLineageProvider,
)
from market.data.historical.nse_symbol_change import (
    NSESymbolChangeRecord,
)
from market.data.historical.security_lineage import (
    SecurityLineageObservation,
)


def make_evidence(
    *,
    snapshot_date: date,
    symbol: str,
    isin: str = "INE000A01000",
    fin_instrm_id: str = "100",
    deletion_flag: str = "N",
) -> NSESecurityMasterEvidence:
    identity = NSESecurityMasterRecord(
        snapshot_date=snapshot_date,
        fin_instrm_id=fin_instrm_id,
        symbol=symbol,
        series="EQ",
        isin=isin,
        exchange="NSE",
    )

    lifecycle = NSESecurityMasterLifecycle(
        listing_date=snapshot_date,
        removal_date=None,
        readmission_date=None,
        normal_market_status="ACTIVE",
        normal_market_eligibility="ELIGIBLE",
        deletion_flag=deletion_flag,
    )

    return NSESecurityMasterEvidence(
        identity=identity,
        lifecycle=lifecycle,
    )


def make_history(*evidence):
    by_date = {}

    for item in evidence:
        by_date.setdefault(
            item.identity.snapshot_date,
            [],
        ).append(item)

    snapshots = tuple(
        NSESecurityMasterEvidenceSnapshot(
            snapshot_date=day,
            evidence=tuple(items),
        )
        for day, items in sorted(by_date.items())
    )

    return NSESecurityMasterObservationHistory(
        snapshots=snapshots,
    )


def make_observation(
    *,
    symbol="RELIANCE",
    isin="INE002A01018",
    fin_instrm_id="2881",
    effective_from=date(2026, 1, 1),
):
    return SecurityLineageObservation(
        fin_instrm_id=fin_instrm_id,
        symbol=symbol,
        series="EQ",
        isin=isin,
        exchange="NSE",
        effective_from=effective_from,
        source="test",
    )


def test_stable_symbol_history_provider():
    history = make_history(
        make_evidence(
            snapshot_date=date(2026, 1, 1),
            symbol="RELIANCE",
            isin="INE002A01018",
            fin_instrm_id="2881",
        ),
        make_evidence(
            snapshot_date=date(2026, 1, 2),
            symbol="RELIANCE",
            isin="INE002A01018",
            fin_instrm_id="2881",
        ),
    )

    provider = NSESecurityMasterHistoryProvider((history,))

    timeline = provider.get_symbol_timeline(
        "INE002A01018",
        "NSE",
    )

    assert timeline.isin == "INE002A01018"
    assert timeline.symbol_on(date(2026, 1, 2)) == "RELIANCE"


def test_multiple_symbols_fail_closed_without_explicit_transition():
    history = make_history(
        make_evidence(
            snapshot_date=date(2026, 1, 1),
            symbol="OLDNAME",
        ),
        make_evidence(
            snapshot_date=date(2026, 1, 2),
            symbol="NEWNAME",
        ),
    )

    provider = NSESecurityMasterHistoryProvider((history,))

    with pytest.raises(ValueError, match="explicit symbol-change evidence"):
        provider.get_symbol_timeline(
            "INE000A01000",
            "NSE",
        )


def test_lineage_provider_accepts_stable_identity():
    observation = make_observation()

    # Constructor requires Security Master history, so use a minimal history.
    evidence = make_evidence(
        snapshot_date=date(2026, 1, 1),
        symbol="RELIANCE",
        isin=observation.isin,
        fin_instrm_id=observation.fin_instrm_id,
    )

    provider = NSESecurityLineageProvider(
        histories=(make_history(evidence),),
        transitions=(),
    )

    lineage = provider.get_security_lineage(observation)

    assert lineage.observation_on(date(2026, 1, 2)) == observation


def test_lineage_provider_requires_explicit_transition_for_rename():
    old = make_evidence(
        snapshot_date=date(2026, 6, 25),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    new = make_evidence(
        snapshot_date=date(2026, 7, 2),
        symbol="NEWNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    history = make_history(old, new)

    transition = NSESymbolChangeRecord(
        company="Test Company",
        old_symbol="OLDNAME",
        new_symbol="NEWNAME",
        effective_date=date(2026, 7, 1),
        source="test",
    )

    provider = NSESecurityLineageProvider(
        histories=(history,),
        transitions=(transition,),
    )

    observation = make_observation(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
        effective_from=date(2026, 1, 1),
    )

    lineage = provider.get_security_lineage(observation)

    resolved = lineage.observation_on(date(2026, 6, 25))
    assert resolved is not None
    assert resolved.symbol == "OLDNAME"
    assert resolved.fin_instrm_id == "100"
    assert resolved.isin == "INE000A01000"


def test_lineage_does_not_infer_identity_continuity():
    old = make_evidence(
        snapshot_date=date(2026, 6, 25),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    new = make_evidence(
        snapshot_date=date(2026, 7, 2),
        symbol="NEWNAME",
        isin="INE999A01099",
        fin_instrm_id="999",
    )

    history = make_history(old, new)

    transition = NSESymbolChangeRecord(
        company="Test Company",
        old_symbol="OLDNAME",
        new_symbol="NEWNAME",
        effective_date=date(2026, 7, 1),
        source="test",
    )

    provider = NSESecurityLineageProvider(
        histories=(history,),
        transitions=(transition,),
    )

    observation = make_observation(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    # Resolver is allowed to corroborate the transition even when identity
    # attributes differ; the provider must not manufacture continuity.
    lineage = provider.get_security_lineage(observation)

    resolved = lineage.observation_on(date(2026, 6, 25))
    assert resolved is not None
    assert resolved.symbol == "OLDNAME"
    assert resolved.fin_instrm_id == "100"
    assert resolved.isin == "INE000A01000"


def test_lineage_provider_rejects_missing_pre_transition_evidence():
    new = make_evidence(
        snapshot_date=date(2026, 7, 2),
        symbol="NEWNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    history = make_history(new)

    transition = NSESymbolChangeRecord(
        company="Test Company",
        old_symbol="OLDNAME",
        new_symbol="NEWNAME",
        effective_date=date(2026, 7, 1),
        source="test",
    )

    provider = NSESecurityLineageProvider(
        histories=(history,),
        transitions=(transition,),
    )

    observation = make_observation(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    with pytest.raises(ValueError, match="no old-symbol observation"):
        provider.get_security_lineage(observation)


def test_lineage_provider_rejects_missing_post_transition_evidence():
    old = make_evidence(
        snapshot_date=date(2026, 6, 25),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    history = make_history(old)

    transition = NSESymbolChangeRecord(
        company="Test Company",
        old_symbol="OLDNAME",
        new_symbol="NEWNAME",
        effective_date=date(2026, 7, 1),
        source="test",
    )

    provider = NSESecurityLineageProvider(
        histories=(history,),
        transitions=(transition,),
    )

    observation = make_observation(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    with pytest.raises(ValueError, match="no new-symbol observation"):
        provider.get_security_lineage(observation)


def test_lineage_provider_rejects_active_old_symbol_after_transition():
    old_before = make_evidence(
        snapshot_date=date(2026, 6, 25),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
        deletion_flag="N",
    )

    old_after = make_evidence(
        snapshot_date=date(2026, 7, 2),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
        deletion_flag="N",
    )

    new_after = make_evidence(
        snapshot_date=date(2026, 7, 3),
        symbol="NEWNAME",
        isin="INE000A01000",
        fin_instrm_id="200",
        deletion_flag="N",
    )

    history = make_history(old_before, old_after, new_after)

    transition = NSESymbolChangeRecord(
        company="Test Company",
        old_symbol="OLDNAME",
        new_symbol="NEWNAME",
        effective_date=date(2026, 7, 1),
        source="test",
    )

    provider = NSESecurityLineageProvider(
        histories=(history,),
        transitions=(transition,),
    )

    observation = make_observation(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    with pytest.raises(ValueError, match="active old-symbol observation exists"):
        provider.get_security_lineage(observation)


def test_lineage_provider_allows_retained_deleted_old_symbol():
    old_before = make_evidence(
        snapshot_date=date(2026, 6, 25),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
        deletion_flag="N",
    )

    old_after_deleted = make_evidence(
        snapshot_date=date(2026, 7, 2),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
        deletion_flag="Y",
    )

    new_after = make_evidence(
        snapshot_date=date(2026, 7, 3),
        symbol="NEWNAME",
        isin="INE000A01000",
        fin_instrm_id="200",
        deletion_flag="N",
    )

    history = make_history(
        old_before,
        old_after_deleted,
        new_after,
    )

    transition = NSESymbolChangeRecord(
        company="Test Company",
        old_symbol="OLDNAME",
        new_symbol="NEWNAME",
        effective_date=date(2026, 7, 1),
        source="test",
    )

    provider = NSESecurityLineageProvider(
        histories=(history,),
        transitions=(transition,),
    )

    observation = make_observation(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    lineage = provider.get_security_lineage(observation)

    assert lineage.observation_on(date(2026, 6, 30)).symbol == "OLDNAME"


def test_lineage_provider_does_not_infer_continuity_from_matching_isin():
    old = make_evidence(
        snapshot_date=date(2026, 6, 25),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    new = make_evidence(
        snapshot_date=date(2026, 7, 2),
        symbol="NEWNAME",
        isin="INE000A01000",
        fin_instrm_id="999",
    )

    transition = NSESymbolChangeRecord(
        company="Test Company",
        old_symbol="OLDNAME",
        new_symbol="NEWNAME",
        effective_date=date(2026, 7, 1),
        source="test",
    )

    provider = NSESecurityLineageProvider(
        histories=(make_history(old, new),),
        transitions=(transition,),
    )

    observation = make_observation(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    lineage = provider.get_security_lineage(observation)

    assert len(lineage.observations) == 2
    assert lineage.observations[0].symbol == "OLDNAME"
    assert lineage.observations[1].symbol == "NEWNAME"
    assert lineage.observations[0].fin_instrm_id == observation.fin_instrm_id
    assert lineage.observations[0].isin == observation.isin


def test_lineage_provider_does_not_infer_continuity_from_matching_fin_instrm_id():
    old = make_evidence(
        snapshot_date=date(2026, 6, 25),
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    new = make_evidence(
        snapshot_date=date(2026, 7, 2),
        symbol="NEWNAME",
        isin="INE999A01099",
        fin_instrm_id="100",
    )

    transition = NSESymbolChangeRecord(
        company="Test Company",
        old_symbol="OLDNAME",
        new_symbol="NEWNAME",
        effective_date=date(2026, 7, 1),
        source="test",
    )

    provider = NSESecurityLineageProvider(
        histories=(make_history(old, new),),
        transitions=(transition,),
    )

    observation = make_observation(
        symbol="OLDNAME",
        isin="INE000A01000",
        fin_instrm_id="100",
    )

    lineage = provider.get_security_lineage(observation)

    assert len(lineage.observations) == 2
    assert lineage.observations[0].symbol == "OLDNAME"
    assert lineage.observations[1].symbol == "NEWNAME"
    assert lineage.observations[0].fin_instrm_id == observation.fin_instrm_id
    assert lineage.observations[0].isin == observation.isin

