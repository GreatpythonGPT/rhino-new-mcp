"""Tests for connection.py — TCP connection management (without real Rhino)."""

import asyncio
import json
import struct

import pytest
from rhino_mcp.connection import RhinoConnection, RhinoConnectionError
from rhino_mcp.protocol import MessageType, RhinoRequest, RhinoResponse, RequestStatus


# ---------------------------------------------------------------------------
# Helpers to create a fake server
# ---------------------------------------------------------------------------

async def start_fake_server(host="localhost", port=19876):
    """Start a minimal TCP server that echoes back valid responses."""
    responses = []

    async def handle_client(reader, writer):
        while True:
            try:
                header = await reader.readexactly(4)
                msg_len = int.from_bytes(header, "big")
                body = await reader.readexactly(msg_len)
                request = json.loads(body.decode("utf-8"))
                req_id = request.get("id", "unknown")
                response = RhinoResponse.make_success(req_id, {"echo": True})
                resp_bytes = response.model_dump_json().encode("utf-8")
                writer.write(len(resp_bytes).to_bytes(4, "big") + resp_bytes)
                await writer.drain()
                responses.append(request)
            except asyncio.IncompleteReadError:
                break

    server = await asyncio.start_server(handle_client, host, port)
    return server, responses


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connection_refused_raises():
    """Connecting to a port with nothing listening should raise RhinoConnectionError."""
    conn = RhinoConnection(host="localhost", port=19999)
    with pytest.raises(RhinoConnectionError):
        await conn.connect()


@pytest.mark.asyncio
async def test_successful_connection_and_request():
    """Test round-trip request/response with a fake server."""
    server, received = await start_fake_server(port=19877)
    async with server:
        conn = RhinoConnection(host="localhost", port=19877)
        await conn.connect()
        assert conn.connected

        req = RhinoRequest(type=MessageType.HEALTH_CHECK, payload={})
        resp = await conn.send_request(req)

        assert resp.status == RequestStatus.SUCCESS
        assert resp.result["echo"] is True
        assert len(received) == 1
        await conn.disconnect()


@pytest.mark.asyncio
async def test_connection_status():
    conn = RhinoConnection(host="localhost", port=19878)
    status = conn.get_status()
    assert status["connected"] is False
    assert status["host"] == "localhost"
    assert status["port"] == 19878
    assert status["uptime_seconds"] is None


@pytest.mark.asyncio
async def test_multiple_requests():
    """Multiple sequential requests should work."""
    server, received = await start_fake_server(port=19879)
    async with server:
        conn = RhinoConnection(host="localhost", port=19879)
        await conn.connect()

        for i in range(3):
            req = RhinoRequest(
                type=MessageType.EXECUTE_COMMAND,
                payload={"code": f"print({i})", "timeout": 5},
            )
            resp = await conn.send_request(req)
            assert resp.status == RequestStatus.SUCCESS

        await conn.disconnect()
        assert len(received) == 3
