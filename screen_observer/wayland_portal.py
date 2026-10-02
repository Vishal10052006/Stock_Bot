from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from typing import Any

from dbus_next import Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType


PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
SCREENCAST_IFACE = "org.freedesktop.portal.ScreenCast"
REQUEST_IFACE = "org.freedesktop.portal.Request"
SESSION_IFACE = "org.freedesktop.portal.Session"

SCREENCAST_XML = """
<node>
  <interface name="org.freedesktop.portal.ScreenCast">
    <method name="CreateSession">
      <arg direction="in" type="a{sv}" name="options"/>
      <arg direction="out" type="o" name="session_handle"/>
    </method>
    <method name="SelectSources">
      <arg direction="in" type="o" name="session_handle"/>
      <arg direction="in" type="a{sv}" name="options"/>
      <arg direction="out" type="o" name="request_handle"/>
    </method>
    <method name="Start">
      <arg direction="in" type="o" name="session_handle"/>
      <arg direction="in" type="s" name="parent_window"/>
      <arg direction="in" type="a{sv}" name="options"/>
      <arg direction="out" type="o" name="request_handle"/>
    </method>
    <method name="OpenPipeWireRemote">
      <arg direction="in" type="o" name="session_handle"/>
      <arg direction="in" type="a{sv}" name="options"/>
      <arg direction="out" type="h" name="pipewire_fd"/>
    </method>
  </interface>
</node>
"""

REQUEST_XML = """
<node>
  <interface name="org.freedesktop.portal.Request">
    <signal name="Response">
      <arg type="u" name="response"/>
      <arg type="a{sv}" name="results"/>
    </signal>
  </interface>
</node>
"""

SESSION_XML = """
<node>
  <interface name="org.freedesktop.portal.Session">
    <method name="Close"/>
  </interface>
</node>
"""


class WaylandScreenCastError(RuntimeError):
    """Raised when the Wayland ScreenCast portal cannot be used."""


@dataclass(frozen=True, slots=True)
class PipeWireStream:
    node_id: int
    properties: dict[str, Any]

    @property
    def pipewire_serial(self) -> int | None:
        value = self.properties.get("pipewire-serial")
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True, slots=True)
class ScreenCastStartResult:
    streams: tuple[PipeWireStream, ...]
    restore_token: str | None


class WaylandScreenCastPortal:
    """
    Thin asynchronous client for the XDG ScreenCast portal.

    The portal owns source selection and session lifetime. This class does
    not interpret pixels, perform OCR, make trading decisions, or place
    orders.
    """

    def __init__(self, *, persist_mode: int = 2) -> None:
        if persist_mode not in (0, 1, 2):
            raise ValueError("persist_mode must be 0, 1, or 2")
        self.persist_mode = persist_mode
        self._bus: MessageBus | None = None
        self._screen_cast = None
        self._session_handle: str | None = None

    async def connect(self) -> None:
        if self._bus is not None:
            return

        self._bus = await MessageBus(
            bus_type=BusType.SESSION,
            negotiate_unix_fd=True,
        ).connect()

        proxy = self._bus.get_proxy_object(
            PORTAL_BUS,
            PORTAL_PATH,
            SCREENCAST_XML,
        )
        self._screen_cast = proxy.get_interface(SCREENCAST_IFACE)

    def _request_path(self, token: str) -> str:
        if self._bus is None or self._bus.unique_name is None:
            raise WaylandScreenCastError("Portal bus is not connected")

        sender = self._bus.unique_name[1:].replace(".", "_")
        return (
            "/org/freedesktop/portal/desktop/request/"
            f"{sender}/{token}"
        )

    async def _prepare_request(
        self,
        token: str,
    ) -> tuple[str, asyncio.Future[tuple[int, dict[str, Variant]]]]:
        if self._bus is None:
            raise WaylandScreenCastError("Portal bus is not connected")

        request_path = self._request_path(token)
        proxy = self._bus.get_proxy_object(
            PORTAL_BUS,
            request_path,
            REQUEST_XML,
        )
        request = proxy.get_interface(REQUEST_IFACE)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[tuple[int, dict[str, Variant]]] = (
            loop.create_future()
        )

        def on_response(
            response: int,
            results: dict[str, Variant],
        ) -> None:
            if not future.done():
                future.set_result((response, results))

        request.on_response(on_response)
        return request_path, future

    @staticmethod
    def _token(prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(12)}"

    async def _finish_request(
        self,
        request_path: str,
        expected_path: str,
        future: asyncio.Future[tuple[int, dict[str, Variant]]],
        operation: str,
    ) -> tuple[int, dict[str, Variant]]:
        if request_path != expected_path:
            raise WaylandScreenCastError(
                f"{operation} returned unexpected request path: "
                f"{request_path!r} != {expected_path!r}"
            )
        try:
            return await asyncio.wait_for(future, timeout=120.0)
        except asyncio.TimeoutError as exc:
            raise WaylandScreenCastError(
                f"{operation} timed out waiting for portal Response"
            ) from exc

    async def create_session(
        self,
        *,
        restore_token: str | None = None,
    ) -> str:
        if self._screen_cast is None:
            await self.connect()
        assert self._screen_cast is not None

        token = self._token("stockbot")
        options: dict[str, Variant] = {
            "handle_token": Variant("s", token),
            "session_handle_token": Variant(
                "s",
                self._token("session"),
            ),
        }
        if restore_token:
            options["restore_token"] = Variant("s", restore_token)

        expected_path, future = await self._prepare_request(token)
        request_path = await self._screen_cast.call_create_session(options)
        response, results = await self._finish_request(
            request_path,
            expected_path,
            future,
            "CreateSession",
        )

        if response != 0:
            raise WaylandScreenCastError(
                f"CreateSession failed: response={response}"
            )

        session_handle_variant = results.get("session_handle")
        if session_handle_variant is None:
            raise WaylandScreenCastError(
                "CreateSession returned no session_handle"
            )

        session_handle = str(session_handle_variant.value)
        self._session_handle = session_handle
        return session_handle

    async def select_sources(
        self,
        *,
        source_types: int = 2,
        multiple: bool = False,
        persist_mode: int | None = None,
        restore_token: str | None = None,
        cursor_mode: int = 1,
    ) -> None:
        if self._screen_cast is None:
            raise WaylandScreenCastError("Portal is not connected")
        if self._session_handle is None:
            raise WaylandScreenCastError(
                "ScreenCast session has not been created"
            )
        if source_types <= 0:
            raise ValueError("source_types must be non-zero")

        if persist_mode is None:
            persist_mode = self.persist_mode

        token = self._token("sources")
        options: dict[str, Variant] = {
            "handle_token": Variant("s", token),
            "types": Variant("u", source_types),
            "multiple": Variant("b", multiple),
            "cursor_mode": Variant("u", cursor_mode),
            "persist_mode": Variant("u", persist_mode),
        }
        if restore_token:
            options["restore_token"] = Variant("s", restore_token)

        expected_path, future = await self._prepare_request(token)
        request_path = await self._screen_cast.call_select_sources(
            self._session_handle,
            options,
        )
        response, _results = await self._finish_request(
            request_path,
            expected_path,
            future,
            "SelectSources",
        )

        if response != 0:
            raise WaylandScreenCastError(
                f"SelectSources failed: response={response}"
            )

    async def start(self, *, parent_window: str = "") -> ScreenCastStartResult:
        if self._screen_cast is None:
            raise WaylandScreenCastError("Portal is not connected")
        if self._session_handle is None:
            raise WaylandScreenCastError(
                "ScreenCast session has not been created"
            )

        token = self._token("start")
        options: dict[str, Variant] = {
            "handle_token": Variant("s", token),
        }

        expected_path, future = await self._prepare_request(token)
        request_path = await self._screen_cast.call_start(
            self._session_handle,
            parent_window,
            options,
        )
        response, results = await self._finish_request(
            request_path,
            expected_path,
            future,
            "Start",
        )

        if response != 0:
            raise WaylandScreenCastError(
                f"Start failed: response={response}"
            )

        raw_streams = results.get("streams")
        if raw_streams is None:
            raise WaylandScreenCastError("Start returned no streams")

        streams = tuple(
            PipeWireStream(
                node_id=int(node_id),
                properties={
                    key: value.value
                    for key, value in properties.items()
                },
            )
            for node_id, properties in raw_streams.value
        )

        restore_variant = results.get("restore_token")
        restore = (
            str(restore_variant.value)
            if restore_variant is not None
            else None
        )

        return ScreenCastStartResult(
            streams=streams,
            restore_token=restore,
        )

    async def open_pipewire_remote(self) -> int:
        if self._screen_cast is None:
            raise WaylandScreenCastError("Portal is not connected")
        if self._session_handle is None:
            raise WaylandScreenCastError(
                "ScreenCast session has not been created"
            )

        fd = await self._screen_cast.call_open_pipe_wire_remote(
            self._session_handle,
            {},
        )
        return int(fd)

    async def close(self) -> None:
        if self._bus is None:
            return

        if self._session_handle:
            try:
                proxy = self._bus.get_proxy_object(
                    PORTAL_BUS,
                    self._session_handle,
                    SESSION_XML,
                )
                session = proxy.get_interface(SESSION_IFACE)
                await session.call_close()
            except Exception:
                # Cleanup must not hide the original failure.
                pass

        self._session_handle = None
        self._screen_cast = None
        self._bus.disconnect()
        self._bus = None

    async def __aenter__(self) -> "WaylandScreenCastPortal":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.close()
