"""TCP socket connection management for communicating with the Rhino plugin.

Handles connect/disconnect, heartbeat, auto-reconnect, and JSON framing.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from .logger import get_logger
from .protocol import MessageType, RhinoRequest, RhinoResponse

logger = get_logger("rhino_mcp.connection")

# Message framing: length-prefixed JSON (4-byte big-endian uint32 + JSON bytes)
HEADER_SIZE = 4
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9876
HEARTBEAT_INTERVAL = 10.0  # seconds
RECONNECT_DELAYS = [2, 4, 8, 16]  # exponential backoff


class RhinoConnectionError(Exception):
    pass


class RhinoConnection:
    """Manages a persistent TCP connection to the Rhino plugin socket server."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._heartbeat_task: asyncio.Task | None = None
        self._connect_lock = asyncio.Lock()
        self.last_command_at: float | None = None
        self.connected_at: float | None = None

    @property
    def connected(self) -> bool:
        return self._connected and self._writer is not None

    async def connect(self) -> None:
        async with self._connect_lock:
            if self.connected:
                return
            for attempt, delay in enumerate([0] + RECONNECT_DELAYS, start=1):
                if delay:
                    logger.info(f"Reconnect attempt {attempt}, waiting {delay}s")
                    await asyncio.sleep(delay)
                try:
                    self._reader, self._writer = await asyncio.open_connection(
                        self.host, self.port
                    )
                    self._connected = True
                    self.connected_at = time.time()
                    logger.info(
                        "Connected to Rhino",
                        extra={"action": "connect", "input": {"host": self.host, "port": self.port}},
                    )
                    self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                    return
                except (ConnectionRefusedError, OSError) as e:
                    logger.warning(f"Connection attempt {attempt} failed: {e}")

            raise RhinoConnectionError(
                f"Failed to connect to Rhino at {self.host}:{self.port} "
                f"after {len(RECONNECT_DELAYS) + 1} attempts. "
                "Make sure the Rhino plugin is loaded and running."
            )

    async def disconnect(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False
        self._reader = None
        self._writer = None
        logger.info("Disconnected from Rhino")

    async def send_request(self, request: RhinoRequest) -> RhinoResponse:
        if not self.connected:
            await self.connect()

        payload = request.model_dump_json().encode("utf-8")
        header = len(payload).to_bytes(HEADER_SIZE, "big")

        try:
            assert self._writer is not None
            self._writer.write(header + payload)
            await self._writer.drain()
            self.last_command_at = time.time()
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            self._connected = False
            raise RhinoConnectionError(f"Send failed: {e}")

        return await self._receive_response(request)

    async def _receive_response(self, request: RhinoRequest) -> RhinoResponse:
        timeout = request.payload.get("timeout", 30)
        try:
            assert self._reader is not None
            header_bytes = await asyncio.wait_for(
                self._reader.readexactly(HEADER_SIZE), timeout=timeout
            )
            msg_len = int.from_bytes(header_bytes, "big")
            if msg_len > 10 * 1024 * 1024:  # 10 MB sanity check
                raise RhinoConnectionError(f"Response too large: {msg_len} bytes")
            body = await asyncio.wait_for(
                self._reader.readexactly(msg_len), timeout=timeout
            )
            data: dict[str, Any] = json.loads(body.decode("utf-8"))
            return RhinoResponse.model_validate(data)
        except asyncio.TimeoutError:
            self._connected = False
            return RhinoResponse.make_timeout(request.id, timeout)
        except (asyncio.IncompleteReadError, ConnectionResetError, OSError) as e:
            self._connected = False
            return RhinoResponse.make_error(
                request.id,
                "ConnectionLost",
                f"Connection lost while waiting for response: {e}",
                "CONNECTION_LOST",
                suggestions=[
                    "Check that Rhino is still running",
                    "Reload the Rhino plugin",
                    "Restart the MCP server",
                ],
            )

    async def _heartbeat_loop(self) -> None:
        while self._connected:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                req = RhinoRequest(type=MessageType.HEALTH_CHECK, payload={})
                await self.send_request(req)
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
                self._connected = False
                break

    def get_status(self) -> dict[str, Any]:
        uptime = None
        if self.connected_at:
            uptime = int(time.time() - self.connected_at)
        return {
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
            "uptime_seconds": uptime,
            "last_command_at": self.last_command_at,
        }
