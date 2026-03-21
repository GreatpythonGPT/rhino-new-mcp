"""Fallback tool: execute arbitrary rhinoscriptsyntax code in Rhino."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..protocol import MessageType, RhinoRequest

if TYPE_CHECKING:
    from ..connection import RhinoConnection
    from ..mock import MockRhinoConnection


async def execute_rhinoscript(
    connection: "RhinoConnection | MockRhinoConnection",
    code: str,
    description: str = "",
    timeout: int = 30,
) -> dict[str, Any]:
    """Execute arbitrary rhinoscriptsyntax code in Rhino.

    This is the fallback tool when no structured tool covers the operation.
    The code runs in Rhino's Python interpreter with rhinoscriptsyntax imported as rs.

    Args:
        connection: Active Rhino connection (real or mock).
        code: rhinoscriptsyntax Python code to execute.
              rhinoscriptsyntax is pre-imported as `rs`.
        description: Human-readable description for logging.
        timeout: Execution timeout in seconds.

    Returns:
        Response dict with created_objects, status, scene_summary.

    Example code::

        import rhinoscriptsyntax as rs
        sphere_id = rs.AddSphere((0, 0, 0), 10)
        rs.ObjectLayer(sphere_id, "MyLayer")
    """
    request = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": code, "description": description, "timeout": timeout},
    )
    response = await connection.send_request(request)
    return response.model_dump()
