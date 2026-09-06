"""Tests for deterministic security-lineage resolution."""

from datetime import date

import pytest

from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)
from market.data.historical.security_lineage_resolution import (
    SecurityLineageResolution,
)
from market.data.historical.security_lineage_resolver import (
    SecurityLineageResolutionError,
    resolve_security_lineage_transition,
)
from market.data.historical.security_lineage_transition import (
    SecurityLineageTransition,
)


TRANSITION_DATE = date(2026, 9, 3)


def make_transition() -> SecurityLineageTransition:
    return SecurityLineageTransition(
        old_symbol="OLD",
        new_symbol="NEW",
        effective_date=TRANSITION_DATE,
        source="test",
    )


def make_observation(
    *,
    observed_on: date,
    symbol: str,
    fin_instrm_id: str,
    isin: str,
    series: str = "EQ",
    exchange: str = "NSE",
) -> NSESecurityMasterObservation:
    return NSESecurityMasterObservation(
        observed_on=observed_on,
        fin_instrm_id=fin_instrm_id,
        symbol=symbol,
        series=series,
        isin=isin,
        exchange=exchange,
    )


def test_resolver_selects_latest_before_and_earliest_after() -> None:
    observations = (
        make_observation(
            observed_on=date(2026, 8, 1),
            symbol="OLD",
            fin_instrm_id="100",
            isin="INE000A01000",
        ),
        make_observation(
            observed_on=date(2026, 9, 2),
            symbol="OLD",
            fin_instrm_id="100",
            isin="INE000A01000",
        ),
        make_observation(
            observed_on=date(2026, 9, 3),
            symbol="NEW",
            fin_instrm_id="200",
            isin="INE000A01001",
        ),
        make_observation(
            observed_on=date(2026, 9, 4),
            symbol="NEW",
            fin_instrm_id="200",
            isin="INE000A01001",
        ),
    )

    result = resolve_security_lineage_transition(
        make_transition(),
        observations,
    )

    assert isinstance(result, SecurityLineageResolution)
    assert result.before.observed_on == date(2026, 9, 2)
    assert result.before.symbol == "OLD"
    assert result.after.observed_on == date(2026, 9, 3)
    assert result.after.symbol == "NEW"


def test_resolver_handles_real_shalimar_paints_symbol_transition() -> None:
    transition = SecurityLineageTransition(
        old_symbol="SHALMPAINT",
        new_symbol="SHALPAINTS",
        effective_date=date(2008, 3, 3),
        source="nse_symbol_change",
    )

    result = resolve_security_lineage_transition(
        transition,
        (
            make_observation(
                observed_on=date(2008, 2, 29),
                symbol="SHALMPAINT",
                fin_instrm_id="3072",
                isin="INE849C01026",
            ),
            make_observation(
                observed_on=date(2008, 3, 3),
                symbol="SHALPAINTS",
                fin_instrm_id="15342",
                isin="INE849C01026",
            ),
        ),
    )

    assert result.before.symbol == "SHALMPAINT"
    assert result.before.fin_instrm_id == "3072"
    assert result.before.isin == "INE849C01026"

    assert result.after.symbol == "SHALPAINTS"
    assert result.after.fin_instrm_id == "15342"
    assert result.after.isin == "INE849C01026"

    assert result.before.fin_instrm_id != result.after.fin_instrm_id
    assert result.before.isin == result.after.isin


def test_resolver_does_not_require_isin_continuity() -> None:
    result = resolve_security_lineage_transition(
        make_transition(),
        (
            make_observation(
                observed_on=date(2026, 9, 2),
                symbol="OLD",
                fin_instrm_id="100",
                isin="INE000A01000",
            ),
            make_observation(
                observed_on=date(2026, 9, 3),
                symbol="NEW",
                fin_instrm_id="200",
                isin="INE000A01099",
            ),
        ),
    )

    assert result.before.isin != result.after.isin


def test_resolver_does_not_require_fin_instrm_id_continuity() -> None:
    result = resolve_security_lineage_transition(
        make_transition(),
        (
            make_observation(
                observed_on=date(2026, 9, 2),
                symbol="OLD",
                fin_instrm_id="100",
                isin="INE000A01000",
            ),
            make_observation(
                observed_on=date(2026, 9, 3),
                symbol="NEW",
                fin_instrm_id="200",
                isin="INE000A01000",
            ),
        ),
    )

    assert result.before.fin_instrm_id != result.after.fin_instrm_id


def test_resolver_rejects_missing_before() -> None:
    with pytest.raises(
        SecurityLineageResolutionError,
        match="no old-symbol observation",
    ):
        resolve_security_lineage_transition(
            make_transition(),
            (
                make_observation(
                    observed_on=date(2026, 9, 3),
                    symbol="NEW",
                    fin_instrm_id="200",
                    isin="INE000A01001",
                ),
            ),
        )


def test_resolver_rejects_missing_after() -> None:
    with pytest.raises(
        SecurityLineageResolutionError,
        match="no new-symbol observation",
    ):
        resolve_security_lineage_transition(
            make_transition(),
            (
                make_observation(
                    observed_on=date(2026, 9, 2),
                    symbol="OLD",
                    fin_instrm_id="100",
                    isin="INE000A01000",
                ),
            ),
        )


def test_resolver_rejects_new_symbol_before_transition() -> None:
    with pytest.raises(
        SecurityLineageResolutionError,
        match="new-symbol observation exists before",
    ):
        resolve_security_lineage_transition(
            make_transition(),
            (
                make_observation(
                    observed_on=date(2026, 9, 2),
                    symbol="OLD",
                    fin_instrm_id="100",
                    isin="INE000A01000",
                ),
                make_observation(
                    observed_on=date(2026, 9, 2),
                    symbol="NEW",
                    fin_instrm_id="200",
                    isin="INE000A01001",
                ),
                make_observation(
                    observed_on=date(2026, 9, 3),
                    symbol="NEW",
                    fin_instrm_id="200",
                    isin="INE000A01001",
                ),
            ),
        )


def test_resolver_rejects_old_symbol_on_or_after_transition() -> None:
    with pytest.raises(
        SecurityLineageResolutionError,
        match="old-symbol observation exists on or after",
    ):
        resolve_security_lineage_transition(
            make_transition(),
            (
                make_observation(
                    observed_on=date(2026, 9, 2),
                    symbol="OLD",
                    fin_instrm_id="100",
                    isin="INE000A01000",
                ),
                make_observation(
                    observed_on=date(2026, 9, 3),
                    symbol="OLD",
                    fin_instrm_id="100",
                    isin="INE000A01000",
                ),
                make_observation(
                    observed_on=date(2026, 9, 3),
                    symbol="NEW",
                    fin_instrm_id="200",
                    isin="INE000A01001",
                ),
            ),
        )


def test_resolver_rejects_duplicate_selected_before_date() -> None:
    with pytest.raises(
        SecurityLineageResolutionError,
        match="multiple old-symbol observations",
    ):
        resolve_security_lineage_transition(
            make_transition(),
            (
                make_observation(
                    observed_on=date(2026, 9, 2),
                    symbol="OLD",
                    fin_instrm_id="100",
                    isin="INE000A01000",
                ),
                make_observation(
                    observed_on=date(2026, 9, 2),
                    symbol="OLD",
                    fin_instrm_id="101",
                    isin="INE000A01001",
                ),
                make_observation(
                    observed_on=date(2026, 9, 3),
                    symbol="NEW",
                    fin_instrm_id="200",
                    isin="INE000A01002",
                ),
            ),
        )


def test_resolver_rejects_duplicate_selected_after_date() -> None:
    with pytest.raises(
        SecurityLineageResolutionError,
        match="multiple new-symbol observations",
    ):
        resolve_security_lineage_transition(
            make_transition(),
            (
                make_observation(
                    observed_on=date(2026, 9, 2),
                    symbol="OLD",
                    fin_instrm_id="100",
                    isin="INE000A01000",
                ),
                make_observation(
                    observed_on=date(2026, 9, 3),
                    symbol="NEW",
                    fin_instrm_id="200",
                    isin="INE000A01001",
                ),
                make_observation(
                    observed_on=date(2026, 9, 3),
                    symbol="NEW",
                    fin_instrm_id="201",
                    isin="INE000A01002",
                ),
            ),
        )


def test_resolver_scopes_series_and_exchange() -> None:
    result = resolve_security_lineage_transition(
        make_transition(),
        (
            make_observation(
                observed_on=date(2026, 9, 2),
                symbol="OLD",
                fin_instrm_id="100",
                isin="INE000A01000",
                series="EQ",
                exchange="NSE",
            ),
            make_observation(
                observed_on=date(2026, 9, 2),
                symbol="OLD",
                fin_instrm_id="101",
                isin="INE000A01001",
                series="BE",
                exchange="NSE",
            ),
            make_observation(
                observed_on=date(2026, 9, 3),
                symbol="NEW",
                fin_instrm_id="200",
                isin="INE000A01002",
                series="EQ",
                exchange="NSE",
            ),
            make_observation(
                observed_on=date(2026, 9, 3),
                symbol="NEW",
                fin_instrm_id="201",
                isin="INE000A01003",
                series="EQ",
                exchange="BSE",
            ),
        ),
    )

    assert result.before.fin_instrm_id == "100"
    assert result.after.fin_instrm_id == "200"


def test_resolver_rejects_no_matching_scope() -> None:
    with pytest.raises(
        SecurityLineageResolutionError,
        match="series and exchange",
    ):
        resolve_security_lineage_transition(
            make_transition(),
            (
                make_observation(
                    observed_on=date(2026, 9, 2),
                    symbol="OLD",
                    fin_instrm_id="100",
                    isin="INE000A01000",
                    series="BE",
                ),
                make_observation(
                    observed_on=date(2026, 9, 3),
                    symbol="NEW",
                    fin_instrm_id="200",
                    isin="INE000A01001",
                    series="BE",
                ),
            ),
        )
