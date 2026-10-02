from screen_observer.wayland_portal import (
    PipeWireStream,
    ScreenCastStartResult,
    WaylandScreenCastPortal,
)


def test_pipewire_stream_serial_is_parsed():
    stream = PipeWireStream(
        node_id=42,
        properties={
            "pipewire-serial": 123456,
        },
    )

    assert stream.node_id == 42
    assert stream.pipewire_serial == 123456


def test_pipewire_stream_without_serial():
    stream = PipeWireStream(
        node_id=42,
        properties={},
    )

    assert stream.pipewire_serial is None


def test_start_result_is_immutable_contract():
    stream = PipeWireStream(
        node_id=42,
        properties={
            "pipewire-serial": 123,
        },
    )

    result = ScreenCastStartResult(
        streams=(stream,),
        restore_token="restore-token",
    )

    assert len(result.streams) == 1
    assert result.streams[0].node_id == 42
    assert result.restore_token == "restore-token"


def test_default_persistence_is_session_persistent():
    portal = WaylandScreenCastPortal()

    assert portal.persist_mode == 2


def test_persistence_mode_validation():
    for value in (-1, 3, 99):
        try:
            WaylandScreenCastPortal(
                persist_mode=value
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"Expected ValueError for {value}"
            )
