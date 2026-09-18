"""Tests for point-in-time historical universe contracts."""

from datetime import date, datetime, timezone

import pytest

from market.data.historical.universe import (
    UniverseMembership,
    UniversePolicy,
    UniverseSnapshot,
)


def test_membership_normalizes_identity():
    membership = UniverseMembership(
        symbol=" reliance ",
        exchange=" nse ",
        effective_from=date(2026, 1, 1),
    )

    assert membership.symbol == "RELIANCE"
    assert membership.exchange == "NSE"


def test_membership_rejects_invalid_interval():
    with pytest.raises(ValueError, match="effective_to"):
        UniverseMembership(
            symbol="RELIANCE",
            exchange="NSE",
            effective_from=date(2026, 2, 1),
            effective_to=date(2026, 1, 1),
        )


def test_membership_rejects_datetime_for_date_fields():
    with pytest.raises(TypeError, match="effective_from"):
        UniverseMembership(
            symbol="RELIANCE",
            exchange="NSE",
            effective_from=datetime(
                2026, 1, 1, tzinfo=timezone.utc
            ),
        )


def test_snapshot_requires_sorted_unique_symbols():
    snapshot = UniverseSnapshot(
        as_of=date(2026, 1, 1),
        policy_version="v1.0",
        symbols=("INFY", "RELIANCE"),
        source="test",
    )

    assert snapshot.symbols == ("INFY", "RELIANCE")
    assert snapshot.contains(" reliance ")
    assert snapshot.contains("INFY")
    assert not snapshot.contains("TCS")


def test_snapshot_rejects_duplicate_symbols():
    with pytest.raises(ValueError, match="duplicates"):
        UniverseSnapshot(
            as_of=date(2026, 1, 1),
            policy_version="v1.0",
            symbols=("INFY", "INFY"),
            source="test",
        )


def test_snapshot_rejects_unsorted_symbols():
    with pytest.raises(ValueError, match="sorted"):
        UniverseSnapshot(
            as_of=date(2026, 1, 1),
            policy_version="v1.0",
            symbols=("RELIANCE", "INFY"),
            source="test",
        )


def test_snapshot_rejects_datetime_for_as_of():
    with pytest.raises(TypeError, match="as_of"):
        UniverseSnapshot(
            as_of=datetime(
                2026, 1, 1, tzinfo=timezone.utc
            ),
            policy_version="v1.0",
            symbols=("INFY",),
            source="test",
        )


def test_policy_is_versioned_and_immutable():
    policy = UniversePolicy(
        version=" v1.0 ",
        name=" Initial liquid NSE equity universe ",
    )

    assert policy.version == "v1.0"
    assert policy.name == "Initial liquid NSE equity universe"

    with pytest.raises(AttributeError):
        policy.version = "v2.0"


def test_policy_requires_identity():
    with pytest.raises(ValueError, match="version"):
        UniversePolicy(version=" ", name="test")

    with pytest.raises(ValueError, match="name"):
        UniversePolicy(version="v1.0", name=" ")


def test_membership_timeline_accepts_independent_instruments():
    from market.data.historical.universe import (
        UniverseMembershipTimeline,
    )

    timeline = UniverseMembershipTimeline(
        (
            UniverseMembership(
                symbol="INFY",
                exchange="NSE",
                effective_from=date(2026, 1, 1),
            ),
            UniverseMembership(
                symbol="RELIANCE",
                exchange="NSE",
                effective_from=date(2026, 1, 1),
            ),
        )
    )

    assert timeline.is_member(
        symbol="INFY",
        exchange="NSE",
        as_of=date(2026, 9, 1),
    )

    assert timeline.is_member(
        symbol="RELIANCE",
        exchange="NSE",
        as_of=date(2026, 9, 1),
    )


def test_membership_timeline_respects_effective_interval():
    from market.data.historical.universe import (
        UniverseMembershipTimeline,
    )

    timeline = UniverseMembershipTimeline(
        (
            UniverseMembership(
                symbol="INFY",
                exchange="NSE",
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 6, 30),
            ),
        )
    )

    assert not timeline.is_member(
        symbol="INFY",
        exchange="NSE",
        as_of=date(2025, 12, 31),
    )

    assert timeline.is_member(
        symbol="INFY",
        exchange="NSE",
        as_of=date(2026, 1, 1),
    )

    assert timeline.is_member(
        symbol="INFY",
        exchange="NSE",
        as_of=date(2026, 6, 30),
    )

    assert not timeline.is_member(
        symbol="INFY",
        exchange="NSE",
        as_of=date(2026, 7, 1),
    )


def test_membership_timeline_rejects_overlapping_intervals():
    from market.data.historical.universe import (
        UniverseMembershipTimeline,
    )

    with pytest.raises(ValueError, match="must not overlap"):
        UniverseMembershipTimeline(
            (
                UniverseMembership(
                    symbol="INFY",
                    exchange="NSE",
                    effective_from=date(2026, 1, 1),
                    effective_to=date(2026, 6, 30),
                ),
                UniverseMembership(
                    symbol="INFY",
                    exchange="NSE",
                    effective_from=date(2026, 6, 30),
                    effective_to=date(2026, 12, 31),
                ),
            )
        )


def test_membership_timeline_rejects_open_ended_interval_before_later_interval():
    from market.data.historical.universe import (
        UniverseMembershipTimeline,
    )

    with pytest.raises(
        ValueError,
        match="open-ended membership",
    ):
        UniverseMembershipTimeline(
            (
                UniverseMembership(
                    symbol="INFY",
                    exchange="NSE",
                    effective_from=date(2026, 1, 1),
                ),
                UniverseMembership(
                    symbol="INFY",
                    exchange="NSE",
                    effective_from=date(2026, 7, 1),
                    effective_to=date(2026, 12, 31),
                ),
            )
        )


def test_membership_timeline_rejects_out_of_order_intervals():
    from market.data.historical.universe import (
        UniverseMembershipTimeline,
    )

    with pytest.raises(
        ValueError,
        match="chronological",
    ):
        UniverseMembershipTimeline(
            (
                UniverseMembership(
                    symbol="INFY",
                    exchange="NSE",
                    effective_from=date(2026, 7, 1),
                    effective_to=date(2026, 12, 31),
                ),
                UniverseMembership(
                    symbol="INFY",
                    exchange="NSE",
                    effective_from=date(2026, 1, 1),
                    effective_to=date(2026, 6, 30),
                ),
            )
        )


def test_membership_timeline_rejects_empty_memberships():
    from market.data.historical.universe import (
        UniverseMembershipTimeline,
    )

    with pytest.raises(ValueError, match="must not be empty"):
        UniverseMembershipTimeline(())


def test_membership_timeline_normalizes_query_identity():
    from market.data.historical.universe import (
        UniverseMembershipTimeline,
    )

    timeline = UniverseMembershipTimeline(
        (
            UniverseMembership(
                symbol="INFY",
                exchange="NSE",
                effective_from=date(2026, 1, 1),
            ),
        )
    )

    assert timeline.is_member(
        symbol=" infy ",
        exchange=" nse ",
        as_of=date(2026, 9, 1),
    )


def test_build_universe_snapshot_selects_liquid_candidates_deterministically():
    from market.data.historical.liquidity import (
        DailyLiquidity,
        LiquidityMeasurement,
    )
    from market.data.historical.universe import build_universe_snapshot

    as_of = date(2026, 9, 5)

    completed_sessions = tuple(
        DailyLiquidity(
            session_date=session_date,
            observation_count=1,
            traded_value=10_000_000_000.0,
            source="nse_security_daily",
        )
        for session_date in (
            date(2026, 8, 7),
            date(2026, 8, 10),
            date(2026, 8, 11),
            date(2026, 8, 12),
            date(2026, 8, 13),
            date(2026, 8, 14),
            date(2026, 8, 17),
            date(2026, 8, 18),
            date(2026, 8, 19),
            date(2026, 8, 20),
            date(2026, 8, 21),
            date(2026, 8, 24),
            date(2026, 8, 25),
            date(2026, 8, 26),
            date(2026, 8, 27),
            date(2026, 8, 28),
            date(2026, 8, 31),
            date(2026, 9, 1),
            date(2026, 9, 2),
            date(2026, 9, 3),
        )
    )

    liquidity_measurements = {
        "RELIANCE": LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=completed_sessions,
            average_traded_value=13_702_714_685.50,
        ),
        "HDFCBANK": LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=completed_sessions,
            average_traded_value=19_259_372_896.50,
        ),
        "INFY": LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=completed_sessions,
            average_traded_value=9_080_625_618.17,
        ),
        "TCS": LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=completed_sessions,
            average_traded_value=5_975_977_071.93,
        ),
    }

    liquidity_policy = __import__(
        "market.data.historical.liquidity",
        fromlist=["LiquidityPolicy"],
    ).LiquidityPolicy(
        version="liquidity-audit-2026-09-05",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=5_000_000_000.0,
    )

    universe_policy = UniversePolicy(
        version="universe-audit-2026-09-05",
        name="liquid-nse-equities",
    )

    snapshot = build_universe_snapshot(
        candidates=("TCS", "INFY", "RELIANCE", "HDFCBANK"),
        exchange="NSE",
        as_of=as_of,
        policy=universe_policy,
        liquidity_measurements=liquidity_measurements,
        liquidity_policy=liquidity_policy,
        source="nse_security_daily",
    )

    assert snapshot.as_of == as_of
    assert snapshot.policy_version == "universe-audit-2026-09-05"
    assert snapshot.source == "nse_security_daily"
    assert snapshot.symbols == (
        "HDFCBANK",
        "INFY",
        "RELIANCE",
        "TCS",
    )


def test_build_universe_snapshot_excludes_candidates_without_liquidity_measurement():
    from datetime import timedelta

    from market.data.historical.liquidity import (
        DailyLiquidity,
        LiquidityMeasurement,
        LiquidityPolicy,
    )
    from market.data.historical.universe import build_universe_snapshot

    as_of = date(2026, 9, 5)

    completed_sessions = tuple(
        DailyLiquidity(
            session_date=date(2026, 8, 10) + timedelta(days=index),
            observation_count=1,
            traded_value=10_000_000_000.0,
            source="nse_security_daily",
        )
        for index in range(20)
    )

    liquidity_measurements = {
        "RELIANCE": LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=completed_sessions,
            average_traded_value=13_000_000_000.0,
        ),
    }

    liquidity_policy = LiquidityPolicy(
        version="liquidity-test-1",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=5_000_000_000.0,
    )

    universe_policy = UniversePolicy(
        version="universe-test-1",
        name="liquid-nse-equities",
    )

    snapshot = build_universe_snapshot(
        candidates=("TCS", "RELIANCE"),
        exchange="NSE",
        as_of=as_of,
        policy=universe_policy,
        liquidity_measurements=liquidity_measurements,
        liquidity_policy=liquidity_policy,
        source="nse_security_daily",
    )

    assert snapshot.symbols == ("RELIANCE",)
    assert snapshot.contains("RELIANCE")
    assert not snapshot.contains("TCS")


def test_build_universe_snapshot_excludes_suspended_candidate():
    from datetime import timedelta

    from market.data.historical.instrument_status import (
        InstrumentStatus,
        InstrumentStatusTimeline,
        InstrumentStatusType,
    )
    from market.data.historical.liquidity import (
        DailyLiquidity,
        LiquidityMeasurement,
        LiquidityPolicy,
    )
    from market.data.historical.universe import build_universe_snapshot

    as_of = date(2026, 9, 5)

    completed_sessions = tuple(
        DailyLiquidity(
            session_date=date(2026, 8, 10) + timedelta(days=index),
            observation_count=1,
            traded_value=10_000_000_000.0,
            source="nse_security_daily",
        )
        for index in range(20)
    )

    liquidity_measurements = {
        "RELIANCE": LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=completed_sessions,
            average_traded_value=13_000_000_000.0,
        ),
        "TCS": LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=completed_sessions,
            average_traded_value=13_000_000_000.0,
        ),
    }

    liquidity_policy = LiquidityPolicy(
        version="liquidity-test-2",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=5_000_000_000.0,
    )

    universe_policy = UniversePolicy(
        version="universe-test-2",
        name="liquid-nse-equities",
    )

    instrument_status = {
        "TCS": InstrumentStatusTimeline(
            (
                InstrumentStatus(
                    symbol="TCS",
                    status=InstrumentStatusType.ACTIVE,
                    effective_from=date(2026, 1, 1),
                    effective_to=date(2026, 8, 31),
                ),
                InstrumentStatus(
                    symbol="TCS",
                    status=InstrumentStatusType.SUSPENDED,
                    effective_from=date(2026, 9, 1),
                ),
            )
        ),
    }

    snapshot = build_universe_snapshot(
        candidates=("TCS", "RELIANCE"),
        exchange="NSE",
        as_of=as_of,
        policy=universe_policy,
        liquidity_measurements=liquidity_measurements,
        liquidity_policy=liquidity_policy,
        instrument_status=instrument_status,
        source="nse_security_daily",
    )

    assert snapshot.symbols == ("RELIANCE",)
    assert snapshot.contains("RELIANCE")
    assert not snapshot.contains("TCS")


def test_build_universe_snapshot_excludes_delisted_candidate():
    from datetime import timedelta

    from market.data.historical.instrument_status import (
        InstrumentStatus,
        InstrumentStatusTimeline,
        InstrumentStatusType,
    )
    from market.data.historical.liquidity import (
        DailyLiquidity,
        LiquidityMeasurement,
        LiquidityPolicy,
    )
    from market.data.historical.universe import build_universe_snapshot

    as_of = date(2026, 9, 5)

    completed_sessions = tuple(
        DailyLiquidity(
            session_date=date(2026, 8, 10) + timedelta(days=index),
            observation_count=1,
            traded_value=10_000_000_000.0,
            source="nse_security_daily",
        )
        for index in range(20)
    )

    liquidity_measurements = {
        "RELIANCE": LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=completed_sessions,
            average_traded_value=13_000_000_000.0,
        ),
        "TCS": LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=completed_sessions,
            average_traded_value=13_000_000_000.0,
        ),
    }

    liquidity_policy = LiquidityPolicy(
        version="liquidity-test-3",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=5_000_000_000.0,
    )

    universe_policy = UniversePolicy(
        version="universe-test-3",
        name="liquid-nse-equities",
    )

    instrument_status = {
        "TCS": InstrumentStatusTimeline(
            (
                InstrumentStatus(
                    symbol="TCS",
                    status=InstrumentStatusType.ACTIVE,
                    effective_from=date(2026, 1, 1),
                    effective_to=date(2026, 8, 31),
                ),
                InstrumentStatus(
                    symbol="TCS",
                    status=InstrumentStatusType.DELISTED,
                    effective_from=date(2026, 9, 1),
                ),
            )
        ),
    }

    snapshot = build_universe_snapshot(
        candidates=("TCS", "RELIANCE"),
        exchange="NSE",
        as_of=as_of,
        policy=universe_policy,
        liquidity_measurements=liquidity_measurements,
        liquidity_policy=liquidity_policy,
        instrument_status=instrument_status,
        source="nse_security_daily",
    )

    assert snapshot.symbols == ("RELIANCE",)
    assert snapshot.contains("RELIANCE")
    assert not snapshot.contains("TCS")


def test_build_universe_snapshot_is_point_in_time():
    from market.data.historical.liquidity import (
        DailyLiquidity,
        LiquidityMeasurement,
        LiquidityPolicy,
    )
    from market.data.historical.universe import build_universe_snapshot

    def make_measurement(as_of, traded_value):
        sessions = tuple(
            DailyLiquidity(
                session_date=date(2026, 8, day),
                observation_count=1,
                traded_value=traded_value,
                source="test",
            )
            for day in range(1, 21)
        )

        return LiquidityMeasurement(
            as_of=as_of,
            lookback_sessions=20,
            completed_sessions=sessions,
            average_traded_value=traded_value,
        )

    liquidity_policy = LiquidityPolicy(
        version="pit-liquidity-v1",
        lookback_sessions=20,
        minimum_completed_sessions=20,
        minimum_average_traded_value=5_000_000_000.0,
    )

    universe_policy = UniversePolicy(
        version="pit-universe-v1",
        name="liquid-nse-equities",
    )

    candidates = (
        "RELIANCE",
        "HDFCBANK",
        "ICICIBANK",
    )

    early_as_of = date(2026, 9, 4)

    early_measurements = {
        "RELIANCE": make_measurement(
            early_as_of,
            13_000_000_000.0,
        ),
        "HDFCBANK": make_measurement(
            early_as_of,
            19_000_000_000.0,
        ),
        "ICICIBANK": make_measurement(
            early_as_of,
            12_000_000_000.0,
        ),
    }

    early = build_universe_snapshot(
        candidates=candidates,
        exchange="NSE",
        as_of=early_as_of,
        policy=universe_policy,
        liquidity_measurements=early_measurements,
        liquidity_policy=liquidity_policy,
        source="test",
    )

    assert early.symbols == (
        "HDFCBANK",
        "ICICIBANK",
        "RELIANCE",
    )

    later_as_of = date(2026, 9, 5)

    later_measurements = {
        "RELIANCE": make_measurement(
            later_as_of,
            13_000_000_000.0,
        ),
        "HDFCBANK": make_measurement(
            later_as_of,
            19_000_000_000.0,
        ),
        "ICICIBANK": make_measurement(
            later_as_of,
            4_000_000_000.0,
        ),
    }

    later = build_universe_snapshot(
        candidates=candidates,
        exchange="NSE",
        as_of=later_as_of,
        policy=universe_policy,
        liquidity_measurements=later_measurements,
        liquidity_policy=liquidity_policy,
        source="test",
    )

    assert later.symbols == (
        "HDFCBANK",
        "RELIANCE",
    )

    assert "ICICIBANK" in early.symbols
    assert "ICICIBANK" not in later.symbols

    mismatched_measurements = dict(early_measurements)

    with pytest.raises(
        ValueError,
        match="liquidity measurement as_of must match",
    ):
        build_universe_snapshot(
            candidates=candidates,
            exchange="NSE",
            as_of=later_as_of,
            policy=universe_policy,
            liquidity_measurements=mismatched_measurements,
            liquidity_policy=liquidity_policy,
            source="test",
        )
