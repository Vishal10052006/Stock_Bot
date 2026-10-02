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

    Responsibilities:
    - create a ScreenCast session
    - select monitor/window sources
    - start the session
    - obtain the PipeWire remote FD
    - close the session

    It does NOT:
    - interpret frames
    - perform OCR
    - detect charts
    - make trading decisions
    - place orders
    """

    def __init__(
        self,
        *,
        persist_mode: int = 2,
    ) -> None:
        if persist_mode not in (0, 1, 2):
            raise ValueError(
                "persist_mode must be 0, 1, or 2"
            )

        self.persist_mode = persist_mode

        self._bus: MessageBus | None = None
        self._screen_cast = None
        self._session_handle: str | None = None

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------

    def _request_path(self, token: str) -> str:
        """
        Build the XDG portal Request object path.

        The request path is derived from:
        - the D-Bus sender unique name
        - the handle_token supplied to the portal request

        We build it BEFORE issuing the portal method call so that the
        Response signal listener can be attached before the response
        arrives.
        """
        if (
            self._bus is None
            or self._bus.unique_name is None
        ):
            raise WaylandScreenCastError(
                "Portal bus is not connected"
            )

        sender = (
            self._bus.unique_name[1:]
            .replace(".", "_")
        )

        return (
            "/org/freedesktop/portal/desktop/request/"
            f"{sender}/{token}"
        )

    async def _prepare_request(
        self,
        token: str,
    ) -> tuple[
        str,
        asyncio.Future[
            tuple[int, dict[str, Variant]]
        ],
    ]:
        """
        Prepare a Request.Response listener BEFORE the
        portal method call is made.

        This avoids the D-Bus/XDG portal response race where
        Response may arrive before the listener is attached.
        """
        if self._bus is None:
            raise WaylandScreenCastError(
                "Portal bus is not connected"
            )

        request_path = self._request_path(token)

        proxy = self._bus.get_proxy_object(
            PORTAL_BUS,
            request_path,
            REQUEST_XML,
        )

        request = proxy.get_interface(
            REQUEST_IFACE
        )

        loop = asyncio.get_running_loop()

        future: asyncio.Future[
            tuple[int, dict[str, Variant]]
        ] = loop.create_future()

        def on_response(
            response: int,
            results: dict[str, Variant],
        ) -> None:
            if not future.done():
                future.set_result(
                    (response, results)
                )

        request.on_response(on_response)

        return request_path, future

    @staticmethod
    def _token(prefix: str) -> str:
        """
        Generate a D-Bus-safe portal handle token.
        """
        return (
            f"{prefix}_{secrets.token_hex(12)}"
        )

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Connect to the user's session D-Bus and prepare
        the ScreenCast portal interface.

        Runtime introspection is intentionally avoided because
        some portal interfaces expose property names that are
        rejected by dbus-next's introspection parser.
        """
        if self._bus is not None:
            return

        self._bus = await MessageBus(
            bus_type=BusType.SESSION,
            negotiate_unix_fd=True,
        ).connect()

        self._screen_cast = (
            self._bus
            .get_proxy_object(
                PORTAL_BUS,
                PORTAL_PATH,
                SCREENCAST_XML,
            )
            .get_interface(
                SCREENCAST_IFACE
            )
        )

    # ------------------------------------------------------------------
    # Create session
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        restore_token: str | None = None,
    ) -> str:
        """
        Create a ScreenCast session.

        Returns:
            D-Bus object path of the created session.
        """
        if self._screen_cast is None:
            await self.connect()

        assert self._screen_cast is not None

        handle_token = self._token(
            "stockbot"
        )

        options: dict[str, Variant] = {
            "handle_token": Variant(
                "s",
                handle_token,
            ),
            "session_handle_token": Variant(
                "s",
                self._token("session"),
            ),
        }

        if restore_token:
            options["restore_token"] = Variant(
                "s",
                restore_token,
            )

        # IMPORTANT:
        # Prepare the Response listener BEFORE
        # calling CreateSession.
        request_path, response_future = (
            await self._prepare_request(
                handle_token
            )
        )

        returned_request_path = (
            await self._screen_cast
            .call_create_session(
                options
            )
        )

        if returned_request_path != request_path:
            raise WaylandScreenCastError(
                "CreateSession returned an "
                "unexpected request path: "
                f"expected={request_path!r}, "
                f"actual={returned_request_path!r}"
            )

        response, results = (
            await response_future
        )

        if response != 0:
            raise WaylandScreenCastError(
                "CreateSession failed: "
                f"response={response}"
            )

        session_handle_variant = (
            results.get("session_handle")
        )

        if session_handle_variant is None:
            raise WaylandScreenCastError(
                "CreateSession returned no "
                "session_handle"
            )

        session_handle = str(
            session_handle_variant.value
        )

        self._session_handle = (
            session_handle
        )

        return session_handle

    # ------------------------------------------------------------------
    # Select sources
    # ------------------------------------------------------------------

    async def select_sources(
        self,
        *,
        source_types: int = 2,
        multiple: bool = False,
        persist_mode: int | None = None,
        restore_token: str | None = None,
        cursor_mode: int = 1,
    ) -> None:
        """
        Select the source to capture.

        source_types:
            1 = monitor
            2 = window
            4 = virtual

        Stock Bot defaults to:
            2 = WINDOW
        """
        if self._screen_cast is None:
            raise WaylandScreenCastError(
                "Portal is not connected"
            )

        if self._session_handle is None:
            raise WaylandScreenCastError(
                "ScreenCast session has not "
                "been created"
            )

        if source_types <= 0:
            raise ValueError(
                "source_types must be non-zero"
            )

        if persist_mode is None:
            persist_mode = self.persist_mode

        handle_token = self._token(
            "sources"
        )

        options: dict[str, Variant] = {
            "handle_token": Variant(
                "s",
                handle_token,
            ),
            "types": Variant(
                "u",
                source_types,
            ),
            "multiple": Variant(
                "b",
                multiple,
            ),
            "cursor_mode": Variant(
                "u",
                cursor_mode,
            ),
            "persist_mode": Variant(
                "u",
                persist_mode,
            ),
        }

        if restore_token:
            options["restore_token"] = Variant(
                "s",
                restore_token,
            )

        # Prepare listener BEFORE portal call.
        request_path, response_future = (
            await self._prepare_request(
                handle_token
            )
        )

        returned_request_path = (
            await self._screen_cast
            .call_select_sources(
                self._session_handle,
                options,
            )
        )

        if returned_request_path != request_path:
            raise WaylandScreenCastError(
                "SelectSources returned an "
                "unexpected request path: "
                f"expected={request_path!r}, "
                f"actual={returned_request_path!r}"
            )

        response, _results = (
            await response_future
        )

        if response != 0:
            raise WaylandScreenCastError(
                "SelectSources failed: "
                f"response={response}"
            )

    # ------------------------------------------------------------------
    # Start ScreenCast
    # ------------------------------------------------------------------

    async def start(
        self,
        *,
        parent_window: str = "",
    ) -> ScreenCastStartResult:
        """
        Start the selected ScreenCast source.

        Returns:
            ScreenCastStartResult containing PipeWire
            stream node information and optional restore token.
        """
        if self._screen_cast is None:
            raise WaylandScreenCastError(
                "Portal is not connected"
            )

        if self._session_handle is None:
            raise WaylandScreenCastError(
                "ScreenCast session has not "
                "been created"
            )

        handle_token = self._token(
            "start"
        )

        options: dict[str, Variant] = {
            "handle_token": Variant(
                "s",
                handle_token,
            )
        }

        # Prepare listener BEFORE portal call.
        request_path, response_future = (
            await self._prepare_request(
                handle_token
            )
        )

        returned_request_path = (
            await self._screen_cast.call_start(
                self._session_handle,
                parent_window,
                options,
            )
        )

        if returned_request_path != request_path:
            raise WaylandScreenCastError(
                "Start returned an unexpected "
                "request path: "
                f"expected={request_path!r}, "
                f"actual={returned_request_path!r}"
            )

        response, results = (
            await response_future
        )

        if response != 0:
            raise WaylandScreenCastError(
                "Start failed: "
                f"response={response}"
            )

        raw_streams = results.get(
            "streams"
        )

        if raw_streams is None:
            raise WaylandScreenCastError(
                "Start returned no streams"
            )

        streams: list[PipeWireStream] = []

        for node_id, properties in (
            raw_streams.value
        ):
            streams.append(
                PipeWireStream(
                    node_id=int(node_id),
                    properties={
                        key: value.value
                        for key, value
                        in properties.items()
                    },
                )
            )

        restore_variant = results.get(
            "restore_token"
        )

        restore = (
            str(restore_variant.value)
            if restore_variant is not None
            else None
        )

        return ScreenCastStartResult(
            streams=tuple(streams),
            restore_token=restore,
        )

    # ------------------------------------------------------------------
    # PipeWire
    # ------------------------------------------------------------------

    async def open_pipewire_remote(self) -> int:
        """
        Open the PipeWire remote connection for the
        current ScreenCast session.

        Returns:
            File descriptor for the PipeWire remote.
        """
        if self._screen_cast is None:
            raise WaylandScreenCastError(
                "Portal is not connected"
            )

        if self._session_handle is None:
            raise WaylandScreenCastError(
                "ScreenCast session has not "
                "been created"
            )

        fd = await (
            self._screen_cast
            .call_open_pipe_wire_remote(
                self._session_handle,
                {},
            )
        )

        return int(fd)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """
        Close the ScreenCast session and D-Bus connection.

        Cleanup errors are intentionally swallowed so they
        cannot hide the original failure.
        """
        if self._bus is None:
            return

        if self._session_handle:
            try:
                proxy = (
                    self._bus
                    .get_proxy_object(
                        PORTAL_BUS,
                        self._session_handle,
                        SESSION_XML,
                    )
                )

                session = (
                    proxy.get_interface(
                        SESSION_IFACE
                    )
                )

                await session.call_close()

            except Exception:
                pass

        self._session_handle = None
        self._screen_cast = None

        self._bus.disconnect()
        self._bus = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(
        self,
    ) -> "WaylandScreenCastPortal":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        await self.close()