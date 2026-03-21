#!/usr/bin/env python3
"""RhinoMCP Health Check Script.

Verifies that all system components are functioning correctly.
Run this to diagnose connection issues before using the MCP server.

Usage:
    python scripts/health_check.py
    python scripts/health_check.py --host localhost --port 9876
"""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def check_python_version() -> dict:
    version = sys.version_info
    ok = version >= (3, 10)
    return {
        "name": "Python Version",
        "status": "ok" if ok else "fail",
        "detail": f"{version.major}.{version.minor}.{version.micro}",
        "required": ">=3.10",
    }


def check_dependencies() -> dict:
    missing = []
    packages = {
        "mcp": "mcp",
        "pydantic": "pydantic",
        "anyio": "anyio",
    }
    for name, import_name in packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(name)

    return {
        "name": "Python Dependencies",
        "status": "ok" if not missing else "fail",
        "detail": f"All installed" if not missing else f"Missing: {', '.join(missing)}",
        "required": "mcp, pydantic, anyio",
    }


def check_rhino_connection(host: str, port: int, timeout: float = 3.0) -> dict:
    """Try a TCP connection to the Rhino plugin socket server."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return {
            "name": "Rhino Socket Connection",
            "status": "ok",
            "detail": f"Connected to {host}:{port}",
        }
    except ConnectionRefusedError:
        return {
            "name": "Rhino Socket Connection",
            "status": "fail",
            "detail": f"Connection refused at {host}:{port}",
            "hint": "Start the Rhino plugin: open Rhino, then run _RunPythonScript on socket_server.py",
        }
    except socket.timeout:
        return {
            "name": "Rhino Socket Connection",
            "status": "fail",
            "detail": f"Timeout connecting to {host}:{port}",
            "hint": "Check that the host/port are correct and Rhino is running",
        }
    except OSError as e:
        return {
            "name": "Rhino Socket Connection",
            "status": "fail",
            "detail": str(e),
        }


async def check_mcp_server_mock() -> dict:
    """Verify the MCP server can start in mock mode."""
    try:
        from rhino_mcp.mock import MockRhinoConnection
        from rhino_mcp.protocol import MessageType, RhinoRequest

        conn = MockRhinoConnection()
        req = RhinoRequest(type=MessageType.HEALTH_CHECK, payload={})
        resp = await conn.send_request(req)
        assert resp.result["mock_mode"] is True
        return {
            "name": "MCP Server (Mock Mode)",
            "status": "ok",
            "detail": "Mock connection works correctly",
        }
    except Exception as e:
        return {
            "name": "MCP Server (Mock Mode)",
            "status": "fail",
            "detail": str(e),
        }


async def check_full_health(host: str, port: int) -> dict:
    """Run a health_check request against real Rhino if connected."""
    import asyncio
    import json
    import struct

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=3.0
        )
        req = {
            "id": "health-check-script",
            "type": "health_check",
            "payload": {},
        }
        body = json.dumps(req).encode("utf-8")
        header = len(body).to_bytes(4, "big")
        writer.write(header + body)
        await writer.drain()

        resp_header = await asyncio.wait_for(reader.readexactly(4), timeout=5.0)
        resp_len = int.from_bytes(resp_header, "big")
        resp_body = await asyncio.wait_for(reader.readexactly(resp_len), timeout=5.0)
        data = json.loads(resp_body.decode("utf-8"))
        writer.close()
        await writer.wait_closed()

        scene = data.get("result", {}).get("scene_status", {})
        return {
            "name": "Rhino Health Response",
            "status": "ok",
            "detail": (
                f"Rhino {data.get('result', {}).get('rhino_version', 'unknown')} | "
                f"Doc: {scene.get('document_name', '?')} | "
                f"Objects: {scene.get('object_count', '?')} | "
                f"Units: {scene.get('unit_system', '?')}"
            ),
        }
    except Exception as e:
        return {
            "name": "Rhino Health Response",
            "status": "skip",
            "detail": f"Skipped (Rhino not connected): {e}",
        }


def print_check(result: dict) -> None:
    status = result["status"]
    icon = {"ok": "✓", "fail": "✗", "skip": "○", "warn": "⚠"}.get(status, "?")
    color = {"ok": "\033[32m", "fail": "\033[31m", "skip": "\033[33m"}.get(status, "")
    reset = "\033[0m"
    print(f"  {color}{icon}{reset}  {result['name']}: {result['detail']}")
    if "hint" in result:
        print(f"       → {result['hint']}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="RhinoMCP Health Check")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print("\n=== RhinoMCP Health Check ===\n")
    checks = [
        check_python_version(),
        check_dependencies(),
        check_rhino_connection(args.host, args.port),
        await check_mcp_server_mock(),
        await check_full_health(args.host, args.port),
    ]

    if args.json:
        print(json.dumps(checks, indent=2))
        return

    for check in checks:
        print_check(check)

    passed = sum(1 for c in checks if c["status"] == "ok")
    failed = sum(1 for c in checks if c["status"] == "fail")
    print(f"\n  {passed} passed, {failed} failed\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
