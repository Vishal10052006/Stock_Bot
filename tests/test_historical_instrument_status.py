"""Tests for instrument lifecycle/status contracts."""

from datetime import date

import pytest

from market.data.historical.instrument_status import (
    InstrumentStatus,
    InstrumentStatusType,
)


def test_active_status_is_supported():
    status = InstrumentStatus(
        symbol="RELIANCE",
        status=InstrumentStatusType.ACTIVE,
        effective_from=date(2026, 1, 1),
    )

    assert status.symbol == "RELIANCE"
    assert status.status is InstrumentStatusType.ACTIVE
    assert status.effective_from == date(2026, 1, 1)
    assert status.effective_to is None


def test_suspended_status_can_have_effective_end():
    status = InstrumentStatus(
        symbol="RELIANCE",
        status=InstrumentStatusType.SUSPENDED,
        effective_from=date(2026, 2, 1),
        effective_to=date(2026, 2, 10),
    )

    assert status.status is InstrumentStatusType.SUSPENDED
    assert status.effective_to == date(2026, 2, 10)


def test_effective_end_must_not_precede_start():
    with pytest.raises(ValueError, match="effective_to"):
        InstrumentStatus(
            symbol="RELIANCE",
            status=InstrumentStatusType.SUSPENDED,
            effective_from=date(2026, 2, 10),
            effective_to=date(2026, 2, 1),
        )


def test_status_requires_non_empty_symbol():
    with pytest.raises(ValueError, match="symbol"):
        InstrumentStatus(
            symbol="",
            status=InstrumentStatusType.ACTIVE,
            effective_from=date(2026, 1, 1),
        )


def test_status_requires_valid_status_type():
    with pytest.raises(TypeError, match="InstrumentStatusType"):
        InstrumentStatus(
            symbol="RELIANCE",
            status="suspended",
            effective_from=date(2026, 1, 1),
        )


def test_datetime_is_rejected_as_effective_from():
    from datetime import datetime

    with pytest.raises(TypeError, match="effective_from must be a date"):
        InstrumentStatus(
            symbol="RELIANCE",
            status=InstrumentStatusType.ACTIVE,
            effective_from=datetime(2026, 1, 1, 9, 15),
        )


def test_datetime_is_rejected_as_effective_to():
    from datetime import datetime

    with pytest.raises(TypeError, match="effective_to must be a date"):
        InstrumentStatus(
            symbol="RELIANCE",
            status=InstrumentStatusType.SUSPENDED,
            effective_from=date(2026, 1, 1),
            effective_to=datetime(2026, 1, 10, 15, 30),
        )


def test_status_timeline_returns_status_for_date():
    from market.data.historical.instrument_status import (
        InstrumentStatusTimeline,
    )

    timeline = InstrumentStatusTimeline(
        (
            InstrumentStatus(
                symbol="RELIANCE",
                status=InstrumentStatusType.ACTIVE,
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 2, 10),
            ),
            InstrumentStatus(
                symbol="RELIANCE",
                status=InstrumentStatusType.SUSPENDED,
                effective_from=date(2026, 2, 11),
                effective_to=date(2026, 2, 15),
            ),
        )
    )

    assert (
        timeline.status_on(date(2026, 1, 15))
        is InstrumentStatusType.ACTIVE
    )
    assert (
        timeline.status_on(date(2026, 2, 12))
        is InstrumentStatusType.SUSPENDED
    )
    assert timeline.status_on(date(2026, 3, 1)) is None


def test_status_timeline_rejects_mixed_symbols():
    from market.data.historical.instrument_status import (
        InstrumentStatusTimeline,
    )

    with pytest.raises(ValueError, match="same symbol"):
        InstrumentStatusTimeline(
            (
                InstrumentStatus(
                    symbol="RELIANCE",
                    status=InstrumentStatusType.ACTIVE,
                    effective_from=date(2026, 1, 1),
                ),
                InstrumentStatus(
                    symbol="TCS",
                    status=InstrumentStatusType.ACTIVE,
                    effective_from=date(2026, 1, 1),
                ),
            )
        )


def test_status_timeline_rejects_overlapping_intervals():
    from market.data.historical.instrument_status import (
        InstrumentStatusTimeline,
    )

    with pytest.raises(ValueError, match="overlap"):
        InstrumentStatusTimeline(
            (
                InstrumentStatus(
                    symbol="RELIANCE",
                    status=InstrumentStatusType.ACTIVE,
                    effective_from=date(2026, 1, 1),
                    effective_to=date(2026, 2, 10),
                ),
                InstrumentStatus(
                    symbol="RELIANCE",
                    status=InstrumentStatusType.SUSPENDED,
                    effective_from=date(2026, 2, 10),
                    effective_to=date(2026, 2, 15),
                ),
            )
        )


def test_status_timeline_rejects_empty_timeline():
    from market.data.historical.instrument_status import (
        InstrumentStatusTimeline,
    )

    with pytest.raises(ValueError, match="at least one"):
        InstrumentStatusTimeline(())


def test_status_timeline_rejects_multiple_open_ended_intervals():
    from market.data.historical.instrument_status import (
        InstrumentStatusTimeline,
    )

    with pytest.raises(ValueError, match="open-ended"):
        InstrumentStatusTimeline(
            (
                InstrumentStatus(
                    symbol="RELIANCE",
                    status=InstrumentStatusType.ACTIVE,
                    effective_from=date(2026, 1, 1),
                ),
                InstrumentStatus(
                    symbol="RELIANCE",
                    status=InstrumentStatusType.SUSPENDED,
                    effective_from=date(2026, 2, 1),
                ),
            )
        )


def test_status_timeline_rejects_open_ended_interval_before_later_status():
    from market.data.historical.instrument_status import (
        InstrumentStatusTimeline,
    )

    with pytest.raises(ValueError, match="open-ended"):
        InstrumentStatusTimeline(
            (
                InstrumentStatus(
                    symbol="RELIANCE",
                    status=InstrumentStatusType.ACTIVE,
                    effective_from=date(2026, 1, 1),
                ),
                InstrumentStatus(
                    symbol="RELIANCE",
                    status=InstrumentStatusType.DELISTED,
                    effective_from=date(2026, 3, 1),
                    effective_to=date(2026, 3, 10),
                ),
            )
        )
