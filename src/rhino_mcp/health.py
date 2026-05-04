"""CLI health check for Rhino MCP server connectivity."""

from __future__ import annotations

import argparse
import asyncio
import json

from .connection import RhinoConnection
from .protocol import MessageType, RhinoRequest


async def _run(host: str, port: int) -> int:
    conn = RhinoConnection(host=host, port=port)
    try:
        await conn.connect()
        req = RhinoRequest(type=MessageType.HEALTH_CHECK, payload={"timeout": 10})
        resp = await conn.send_request(req)
        print(json.dumps(resp.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0 if resp.status.value in {"success", "mock"} else 1
    finally:
        await conn.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Rhino MCP health check")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9876)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.host, args.port)))


if __name__ == "__main__":
    main()
