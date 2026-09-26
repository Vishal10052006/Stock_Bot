"""Tests for deterministic M20 shadow-session manifests."""

from runtime.shadow_manifest import ShadowSessionManifest


def test_manifest_fingerprint_is_deterministic() -> None:
    kwargs = {
        "session_id": "m20-test",
        "mode": "SHADOW",
        "live_broker_order_submission": False,
        "symbols": ("ITC", "TCS"),
        "timeframe_minutes": 5,
        "candles_completed": 12,
        "journal_event_count": 14,
    }

    first = ShadowSessionManifest(**kwargs)
    second = ShadowSessionManifest(**kwargs)

    assert first.fingerprint == second.fingerprint
    assert first.evidence()["manifest_fingerprint"] == first.fingerprint


def test_manifest_rejects_live_execution() -> None:
    try:
        ShadowSessionManifest(
            session_id="unsafe",
            mode="SHADOW",
            live_broker_order_submission=True,
            symbols=("ITC",),
            timeframe_minutes=5,
            candles_completed=0,
            journal_event_count=0,
        )
    except ValueError as exc:
        assert "live broker" in str(exc)
    else:
        raise AssertionError("expected live-order rejection")


def test_manifest_rejects_non_shadow_mode() -> None:
    try:
        ShadowSessionManifest(
            session_id="unsafe",
            mode="LIVE",
            live_broker_order_submission=False,
            symbols=("ITC",),
            timeframe_minutes=5,
            candles_completed=0,
            journal_event_count=0,
        )
    except ValueError as exc:
        assert "SHADOW" in str(exc)
    else:
        raise AssertionError("expected SHADOW mode rejection")
