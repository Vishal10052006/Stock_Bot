"""Tests for corroborated security-lineage transitions."""

from datetime import date

import pytest

from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)
from market.data.historical.security_lineage_resolution import (
    SecurityLineageResolution,
)
from market.data.historical.security_lineage_transition import (
    SecurityLineageTransition,
)


def make_transition() -> SecurityLineageTransition:
    return SecurityLineageTransition(
        old_symbol="OLD",
        new_symbol="NEW",
        effective_date=date(2026, 9, 3),
        source="test",
    )


def make_observation(
    *,
    observed_on: date,
    symbol: str,
    fin_instrm_id: str,
    isin: str,
) -> NSESecurityMasterObservation:
    return NSESecurityMasterObservation(
        observed_on=observed_on,
        fin_instrm_id=fin_instrm_id,
        symbol=symbol,
        series="EQ",
        isin=isin,
        exchange="NSE",
    )


def test_resolution_preserves_transition_and_observations() -> None:
    transition = make_transition()

    before = make_observation(
        observed_on=date(2026, 9, 2),
        symbol="OLD",
        fin_instrm_id="100",
        isin="INE000A01000",
    )

    after = make_observation(
        observed_on=date(2026, 9, 3),
        symbol="NEW",
        fin_instrm_id="200",
        isin="INE000A01001",
    )

    resolution = SecurityLineageResolution(
        transition=transition,
        before=before,
        after=after,
    )

    assert resolution.transition == transition
    assert resolution.before == before
    assert resolution.after == after


def test_before_must_precede_transition() -> None:
    with pytest.raises(ValueError, match="before observation"):
        SecurityLineageResolution(
            transition=make_transition(),
            before=make_observation(
                observed_on=date(2026, 9, 3),
                symbol="OLD",
                fin_instrm_id="100",
                isin="INE000A01000",
            ),
            after=make_observation(
                observed_on=date(2026, 9, 3),
                symbol="NEW",
                fin_instrm_id="200",
                isin="INE000A01001",
            ),
        )


def test_after_must_be_on_or_after_transition() -> None:
    with pytest.raises(ValueError, match="after observation"):
        SecurityLineageResolution(
            transition=make_transition(),
            before=make_observation(
                observed_on=date(2026, 9, 2),
                symbol="OLD",
                fin_instrm_id="100",
                isin="INE000A01000",
            ),
            after=make_observation(
                observed_on=date(2026, 9, 2),
                symbol="NEW",
                fin_instrm_id="200",
                isin="INE000A01001",
            ),
        )


def test_before_symbol_must_match_transition() -> None:
    with pytest.raises(ValueError, match="old_symbol"):
        SecurityLineageResolution(
            transition=make_transition(),
            before=make_observation(
                observed_on=date(2026, 9, 2),
                symbol="WRONG",
                fin_instrm_id="100",
                isin="INE000A01000",
            ),
            after=make_observation(
                observed_on=date(2026, 9, 3),
                symbol="NEW",
                fin_instrm_id="200",
                isin="INE000A01001",
            ),
        )


def test_after_symbol_must_match_transition() -> None:
    with pytest.raises(ValueError, match="new_symbol"):
        SecurityLineageResolution(
            transition=make_transition(),
            before=make_observation(
                observed_on=date(2026, 9, 2),
                symbol="OLD",
                fin_instrm_id="100",
                isin="INE000A01000",
            ),
            after=make_observation(
                observed_on=date(2026, 9, 3),
                symbol="WRONG",
                fin_instrm_id="200",
                isin="INE000A01001",
            ),
        )


@pytest.mark.parametrize(
    "field",
    ["transition", "before", "after"],
)
def test_resolution_rejects_wrong_types(field: str) -> None:
    transition = make_transition()

    values = {
        "transition": transition,
        "before": make_observation(
            observed_on=date(2026, 9, 2),
            symbol="OLD",
            fin_instrm_id="100",
            isin="INE000A01000",
        ),
        "after": make_observation(
            observed_on=date(2026, 9, 3),
            symbol="NEW",
            fin_instrm_id="200",
            isin="INE000A01001",
        ),
    }

    values[field] = object()

    with pytest.raises(TypeError, match=field):
        SecurityLineageResolution(**values)
