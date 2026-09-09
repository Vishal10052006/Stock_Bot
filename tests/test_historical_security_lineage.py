"""Tests for verified point-in-time security lineage."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from market.data.historical.security_lineage import (
    SecurityLineage,
    SecurityLineageObservation,
)


def make_observation(
    *,
    fin_instrm_id: str = "3072",
    symbol: str = "SHALMPAINT",
    series: str = "EQ",
    isin: str = "INE849C01026",
    exchange: str = "NSE",
    effective_from: date = date(2008, 1, 1),
    effective_to: date | None = None,
    source: str = "nse_symbol_change",
) -> SecurityLineageObservation:
    return SecurityLineageObservation(
        fin_instrm_id=fin_instrm_id,
        symbol=symbol,
        series=series,
        isin=isin,
        exchange=exchange,
        effective_from=effective_from,
        effective_to=effective_to,
        source=source,
    )


def test_observation_normalizes_values() -> None:
    observation = make_observation(
        fin_instrm_id=" 3072 ",
        symbol=" shalmpaint ",
        series=" eq ",
        isin=" ine849c01026 ",
        exchange=" nse ",
        source=" nse_symbol_change ",
    )

    assert observation.fin_instrm_id == "3072"
    assert observation.symbol == "SHALMPAINT"
    assert observation.series == "EQ"
    assert observation.isin == "INE849C01026"
    assert observation.exchange == "NSE"
    assert observation.source == "nse_symbol_change"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fin_instrm_id", ""),
        ("symbol", ""),
        ("series", ""),
        ("isin", ""),
        ("exchange", ""),
        ("source", ""),
    ],
)
def test_observation_rejects_empty_fields(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=field):
        make_observation(**{field: value})


def test_observation_requires_effective_from() -> None:
    with pytest.raises(TypeError):
        SecurityLineageObservation(
            fin_instrm_id="3072",
            symbol="SHALMPAINT",
            series="EQ",
            isin="INE849C01026",
            exchange="NSE",
            effective_from=None,  # type: ignore[arg-type]
            source="nse_symbol_change",
        )


def test_observation_rejects_reversed_dates() -> None:
    with pytest.raises(ValueError, match="effective_to"):
        make_observation(
            effective_from=date(2008, 3, 3),
            effective_to=date(2008, 3, 2),
        )


def test_lineage_preserves_distinct_records_with_same_isin() -> None:
    lineage = SecurityLineage(
        lineage_id="NSE-LINEAGE-SHALIMAR-PAINTS",
        observations=(
            make_observation(
                fin_instrm_id="3072",
                symbol="SHALMPAINT",
                effective_from=date(2008, 1, 1),
                effective_to=date(2008, 3, 2),
            ),
            make_observation(
                fin_instrm_id="15342",
                symbol="SHALPAINTS",
                effective_from=date(2008, 3, 3),
            ),
        ),
    )

    old = lineage.observation_on(date(2008, 3, 2))
    new = lineage.observation_on(date(2008, 3, 3))

    assert old is not None
    assert new is not None
    assert old.fin_instrm_id == "3072"
    assert old.symbol == "SHALMPAINT"
    assert new.fin_instrm_id == "15342"
    assert new.symbol == "SHALPAINTS"
    assert old.isin == new.isin


def test_lineage_supports_isin_change_with_same_fin_instrm_id() -> None:
    lineage = SecurityLineage(
        lineage_id="NSE-LINEAGE-TCC",
        observations=(
            make_observation(
                fin_instrm_id="761814",
                symbol="TCC",
                isin="INE887D01016",
                effective_from=date(2026, 9, 1),
                effective_to=date(2026, 9, 2),
            ),
            make_observation(
                fin_instrm_id="761814",
                symbol="TCC",
                isin="INE887D01024",
                effective_from=date(2026, 9, 3),
            ),
        ),
    )

    before = lineage.observation_on(date(2026, 9, 2))
    after = lineage.observation_on(date(2026, 9, 3))

    assert before is not None
    assert after is not None
    assert before.fin_instrm_id == after.fin_instrm_id
    assert before.isin != after.isin


def test_lineage_rejects_mixed_exchanges() -> None:
    with pytest.raises(ValueError, match="same exchange"):
        SecurityLineage(
            lineage_id="LINEAGE-1",
            observations=(
                make_observation(exchange="NSE"),
                make_observation(
                    exchange="BSE",
                    effective_from=date(2020, 1, 2),
                ),
            ),
        )


def test_lineage_rejects_overlapping_observations() -> None:
    with pytest.raises(ValueError, match="must not overlap"):
        SecurityLineage(
            lineage_id="LINEAGE-1",
            observations=(
                make_observation(
                    effective_from=date(2020, 1, 1),
                    effective_to=date(2020, 1, 5),
                ),
                make_observation(
                    symbol="NEWNAME",
                    effective_from=date(2020, 1, 5),
                ),
            ),
        )


def test_lineage_is_automatically_chronological() -> None:
    lineage = SecurityLineage(
        lineage_id="LINEAGE-1",
        observations=(
            make_observation(
                symbol="NEWNAME",
                effective_from=date(2024, 7, 1),
            ),
            make_observation(
                symbol="OLDNAME",
                effective_from=date(2020, 1, 1),
                effective_to=date(2024, 6, 30),
            ),
        ),
    )

    assert lineage.observations[0].symbol == "OLDNAME"
    assert lineage.observations[1].symbol == "NEWNAME"


def test_lineage_returns_none_before_known_history() -> None:
    lineage = SecurityLineage(
        lineage_id="LINEAGE-1",
        observations=(make_observation(),),
    )

    assert lineage.observation_on(date(2007, 12, 31)) is None


def test_lineage_is_immutable() -> None:
    lineage = SecurityLineage(
        lineage_id="LINEAGE-1",
        observations=(make_observation(),),
    )

    with pytest.raises(FrozenInstanceError):
        lineage.lineage_id = "OTHER"  # type: ignore[misc]
