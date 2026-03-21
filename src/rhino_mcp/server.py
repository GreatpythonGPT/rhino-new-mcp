"""RhinoMCP Server — Main entry point.

Implements the MCP protocol using Anthropic's official mcp SDK.
Exposes all Rhino tools to AI agents via standard MCP tool calls.
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .connection import RhinoConnection
from .logger import get_logger
from .mock import MockRhinoConnection
from .protocol import MessageType, RhinoRequest
from .tools import (
    boolean,
    execute,
    geometry,
    layers,
    scene,
    selection,
    surface,
    transform,
    viewport,
)

logger = get_logger("rhino_mcp.server")

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_connection: RhinoConnection | MockRhinoConnection | None = None
_mock_mode: bool = False
_start_time: float = time.time()


def get_connection() -> RhinoConnection | MockRhinoConnection:
    assert _connection is not None, "Connection not initialized"
    return _connection


# ---------------------------------------------------------------------------
# MCP Server setup
# ---------------------------------------------------------------------------

app = Server("rhino-mcp")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """Advertise all available Rhino tools to the MCP client."""
    return [
        # ── Fallback ──────────────────────────────────────────────────────
        types.Tool(
            name="execute_rhinoscript",
            description=(
                "Execute arbitrary rhinoscriptsyntax code in Rhino. "
                "Use as a fallback when no structured tool covers the operation. "
                "rhinoscriptsyntax is pre-imported as 'rs'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "description": {"type": "string", "description": "Purpose of this code"},
                    "timeout": {"type": "integer", "default": 30},
                },
                "required": ["code"],
            },
        ),
        # ── Geometry ──────────────────────────────────────────────────────
        types.Tool(
            name="create_sphere",
            description="Create a sphere at a given center point with a radius.",
            inputSchema={
                "type": "object",
                "properties": {
                    "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "radius": {"type": "number"},
                    "layer": {"type": "string", "default": ""},
                },
                "required": ["center", "radius"],
            },
        ),
        types.Tool(
            name="create_box",
            description="Create a rectangular solid (box) from a corner point with width/depth/height.",
            inputSchema={
                "type": "object",
                "properties": {
                    "corner": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "width": {"type": "number", "description": "Size along X axis (mm)"},
                    "depth": {"type": "number", "description": "Size along Y axis (mm)"},
                    "height": {"type": "number", "description": "Size along Z axis (mm)"},
                    "layer": {"type": "string", "default": ""},
                },
                "required": ["corner", "width", "depth", "height"],
            },
        ),
        types.Tool(
            name="create_cylinder",
            description="Create a vertical cylinder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "base_center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "height": {"type": "number"},
                    "radius": {"type": "number"},
                    "layer": {"type": "string", "default": ""},
                },
                "required": ["base_center", "height", "radius"],
            },
        ),
        types.Tool(
            name="create_cone",
            description="Create a cone.",
            inputSchema={
                "type": "object",
                "properties": {
                    "base_center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "height": {"type": "number"},
                    "radius": {"type": "number"},
                    "layer": {"type": "string", "default": ""},
                },
                "required": ["base_center", "height", "radius"],
            },
        ),
        types.Tool(
            name="create_torus",
            description="Create a torus (donut shape).",
            inputSchema={
                "type": "object",
                "properties": {
                    "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "major_radius": {"type": "number"},
                    "minor_radius": {"type": "number"},
                    "layer": {"type": "string", "default": ""},
                },
                "required": ["center", "major_radius", "minor_radius"],
            },
        ),
        types.Tool(
            name="create_line",
            description="Create a line curve between two points.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "end": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "layer": {"type": "string", "default": ""},
                },
                "required": ["start", "end"],
            },
        ),
        types.Tool(
            name="create_circle",
            description="Create a circle curve.",
            inputSchema={
                "type": "object",
                "properties": {
                    "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "radius": {"type": "number"},
                    "normal": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 1]},
                    "layer": {"type": "string", "default": ""},
                },
                "required": ["center", "radius"],
            },
        ),
        types.Tool(
            name="create_polyline",
            description="Create a polyline through a list of points.",
            inputSchema={
                "type": "object",
                "properties": {
                    "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}},
                    "layer": {"type": "string", "default": ""},
                },
                "required": ["points"],
            },
        ),
        types.Tool(
            name="extrude_curve",
            description="Extrude a profile curve along a direction vector to create a solid.",
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_curve_id": {"type": "string"},
                    "direction": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "cap": {"type": "boolean", "default": True},
                    "layer": {"type": "string", "default": ""},
                },
                "required": ["profile_curve_id", "direction"],
            },
        ),
        # ── Transform ─────────────────────────────────────────────────────
        types.Tool(
            name="move_object",
            description="Move or copy an object by a translation vector.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "translation": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "copy": {"type": "boolean", "default": False},
                },
                "required": ["object_id", "translation"],
            },
        ),
        types.Tool(
            name="rotate_object",
            description="Rotate an object around an axis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "angle_degrees": {"type": "number"},
                    "axis": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 1]},
                    "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                    "copy": {"type": "boolean", "default": False},
                },
                "required": ["object_id", "angle_degrees"],
            },
        ),
        types.Tool(
            name="scale_object",
            description="Scale an object uniformly or non-uniformly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "scale": {"oneOf": [{"type": "number"}, {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}]},
                    "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                    "copy": {"type": "boolean", "default": False},
                },
                "required": ["object_id", "scale"],
            },
        ),
        types.Tool(
            name="mirror_object",
            description="Mirror an object across a plane.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "mirror_plane_point1": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "mirror_plane_point2": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "copy": {"type": "boolean", "default": True},
                },
                "required": ["object_id", "mirror_plane_point1", "mirror_plane_point2"],
            },
        ),
        types.Tool(
            name="array_linear",
            description="Create a linear array of copies along a direction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "count": {"type": "integer"},
                    "direction": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                },
                "required": ["object_id", "count", "direction"],
            },
        ),
        types.Tool(
            name="array_polar",
            description="Create a polar (rotational) array of copies around a center.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "count": {"type": "integer"},
                    "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "axis": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 1]},
                },
                "required": ["object_id", "count", "center"],
            },
        ),
        # ── Boolean ───────────────────────────────────────────────────────
        types.Tool(
            name="boolean_difference",
            description=(
                "Subtract one or more closed solids from another (Boolean Difference). "
                "All objects must be closed watertight solids and must intersect."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "object_a": {"type": "string", "description": "GUID of object to subtract FROM"},
                    "objects_b": {"type": "array", "items": {"type": "string"}, "description": "GUIDs to subtract"},
                    "delete_input": {"type": "boolean", "default": True},
                },
                "required": ["object_a", "objects_b"],
            },
        ),
        types.Tool(
            name="boolean_union",
            description="Join multiple closed solids into one (Boolean Union).",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_ids": {"type": "array", "items": {"type": "string"}},
                    "delete_input": {"type": "boolean", "default": True},
                },
                "required": ["object_ids"],
            },
        ),
        types.Tool(
            name="boolean_intersection",
            description="Keep only the overlapping volume of multiple solids (Boolean Intersection).",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_ids": {"type": "array", "items": {"type": "string"}},
                    "delete_input": {"type": "boolean", "default": True},
                },
                "required": ["object_ids"],
            },
        ),
        types.Tool(
            name="fillet_edges",
            description="Apply round fillet to edges of a solid.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "edge_indices": {"type": "array", "items": {"type": "integer"}, "nullable": True, "description": "Edge indices to fillet, null=all"},
                    "radius": {"type": "number"},
                },
                "required": ["object_id", "radius"],
            },
        ),
        # ── Surface ───────────────────────────────────────────────────────
        types.Tool(
            name="loft",
            description="Create a lofted surface through a series of cross-section curves.",
            inputSchema={
                "type": "object",
                "properties": {
                    "curve_ids": {"type": "array", "items": {"type": "string"}},
                    "loft_type": {"type": "integer", "default": 0, "description": "0=Normal,1=Loose,2=Tight,3=Straight"},
                    "closed": {"type": "boolean", "default": False},
                },
                "required": ["curve_ids"],
            },
        ),
        types.Tool(
            name="sweep1",
            description="Create a sweep surface along a single rail curve.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rail_id": {"type": "string"},
                    "profile_ids": {"type": "array", "items": {"type": "string"}},
                    "closed": {"type": "boolean", "default": False},
                },
                "required": ["rail_id", "profile_ids"],
            },
        ),
        types.Tool(
            name="sweep2",
            description="Create a sweep surface along two rail curves.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rail1_id": {"type": "string"},
                    "rail2_id": {"type": "string"},
                    "profile_ids": {"type": "array", "items": {"type": "string"}},
                    "closed": {"type": "boolean", "default": False},
                },
                "required": ["rail1_id", "rail2_id", "profile_ids"],
            },
        ),
        types.Tool(
            name="revolve",
            description="Revolve a profile curve around an axis to create a surface of revolution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "profile_id": {"type": "string"},
                    "axis_start": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "axis_end": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "start_angle": {"type": "number", "default": 0},
                    "end_angle": {"type": "number", "default": 360},
                },
                "required": ["profile_id", "axis_start", "axis_end"],
            },
        ),
        types.Tool(
            name="pipe",
            description="Create a pipe along a rail curve.",
            inputSchema={
                "type": "object",
                "properties": {
                    "rail_id": {"type": "string"},
                    "radius": {"oneOf": [{"type": "number"}, {"type": "array", "items": {"type": "number"}}]},
                    "cap_mode": {"type": "integer", "default": 1, "description": "0=None,1=Flat,2=Round"},
                },
                "required": ["rail_id", "radius"],
            },
        ),
        types.Tool(
            name="offset_surface",
            description="Offset a surface or solid by a distance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "surface_id": {"type": "string"},
                    "distance": {"type": "number", "description": "Positive=outward, negative=inward"},
                    "solid": {"type": "boolean", "default": False},
                },
                "required": ["surface_id", "distance"],
            },
        ),
        # ── Selection ─────────────────────────────────────────────────────
        types.Tool(
            name="select_by_layer",
            description="Get all object GUIDs on a specific layer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {"type": "string"},
                },
                "required": ["layer_name"],
            },
        ),
        types.Tool(
            name="select_by_type",
            description="Get all object GUIDs matching a type (curve, surface, brep, mesh, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_type": {"type": "string"},
                },
                "required": ["object_type"],
            },
        ),
        types.Tool(
            name="select_closest_to_point",
            description="Find the N closest objects to a point.",
            inputSchema={
                "type": "object",
                "properties": {
                    "point": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "count": {"type": "integer", "default": 1},
                    "object_type": {"type": "string", "nullable": True},
                },
                "required": ["point"],
            },
        ),
        types.Tool(
            name="get_all_objects",
            description="Get a list of all objects in the Rhino document.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # ── Viewport ──────────────────────────────────────────────────────
        types.Tool(
            name="capture_viewport",
            description="Capture a screenshot of a Rhino viewport.",
            inputSchema={
                "type": "object",
                "properties": {
                    "view_name": {"type": "string", "default": "Perspective"},
                    "width": {"type": "integer", "default": 1280},
                    "height": {"type": "integer", "default": 720},
                    "annotate_objects": {"type": "array", "items": {"type": "string"}, "default": []},
                },
            },
        ),
        types.Tool(
            name="set_standard_view",
            description="Switch to a standard view: Top, Front, Right, Perspective, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "view_name": {"type": "string", "default": "Perspective"},
                    "target_object_id": {"type": "string", "nullable": True},
                },
            },
        ),
        types.Tool(
            name="zoom_to_object",
            description="Zoom viewport to frame a specific object.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "view_name": {"type": "string", "default": "Perspective"},
                },
                "required": ["object_id"],
            },
        ),
        # ── Scene ─────────────────────────────────────────────────────────
        types.Tool(
            name="get_scene_state",
            description="Get a full snapshot of the current Rhino document state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_geometry": {"type": "boolean", "default": False},
                },
            },
        ),
        types.Tool(
            name="get_object_info",
            description="Get detailed info (type, layer, bbox, area/volume) about a specific object.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                },
                "required": ["object_id"],
            },
        ),
        types.Tool(
            name="delete_objects",
            description="Delete one or more objects from the document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["object_ids"],
            },
        ),
        types.Tool(
            name="set_object_name",
            description="Assign a name to an object for later reference.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["object_id", "name"],
            },
        ),
        types.Tool(
            name="undo",
            description="Undo the last N operations in Rhino.",
            inputSchema={
                "type": "object",
                "properties": {
                    "steps": {"type": "integer", "default": 1},
                },
            },
        ),
        # ── Layers ────────────────────────────────────────────────────────
        types.Tool(
            name="create_layer",
            description="Create a new layer in Rhino.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "color": {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3, "default": [0, 0, 0]},
                    "parent": {"type": "string", "default": ""},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="set_object_layer",
            description="Move an object to a specific layer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "object_id": {"type": "string"},
                    "layer_name": {"type": "string"},
                },
                "required": ["object_id", "layer_name"],
            },
        ),
        types.Tool(
            name="get_all_layers",
            description="Get a list of all layers with their properties.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # ── Health ────────────────────────────────────────────────────────
        types.Tool(
            name="health_check",
            description="Check server health, Rhino connection status, and scene info.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Dispatch tool calls to the appropriate handler."""
    conn = get_connection()
    try:
        result = await _dispatch(conn, name, arguments)
    except Exception as exc:
        logger.exception(f"Tool '{name}' raised exception")
        result = {"status": "error", "error": {"type": "InternalError", "message": str(exc)}}

    import json
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def _dispatch(
    conn: RhinoConnection | MockRhinoConnection,
    name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Route tool name to the correct function."""
    # ── Fallback ──────────────────────────────────────────────────────────
    if name == "execute_rhinoscript":
        return await execute.execute_rhinoscript(
            conn,
            args["code"],
            args.get("description", ""),
            args.get("timeout", 30),
        )

    # ── Geometry ──────────────────────────────────────────────────────────
    if name == "create_sphere":
        return await geometry.create_sphere(conn, tuple(args["center"]), args["radius"], args.get("layer", ""))
    if name == "create_box":
        return await geometry.create_box(conn, tuple(args["corner"]), args["width"], args["depth"], args["height"], args.get("layer", ""))
    if name == "create_cylinder":
        return await geometry.create_cylinder(conn, tuple(args["base_center"]), args["height"], args["radius"], args.get("layer", ""))
    if name == "create_cone":
        return await geometry.create_cone(conn, tuple(args["base_center"]), args["height"], args["radius"], args.get("layer", ""))
    if name == "create_torus":
        return await geometry.create_torus(conn, tuple(args["center"]), args["major_radius"], args["minor_radius"], args.get("layer", ""))
    if name == "create_line":
        return await geometry.create_line(conn, tuple(args["start"]), tuple(args["end"]), args.get("layer", ""))
    if name == "create_circle":
        return await geometry.create_circle(conn, tuple(args["center"]), args["radius"], tuple(args.get("normal", [0, 0, 1])), args.get("layer", ""))
    if name == "create_polyline":
        return await geometry.create_polyline(conn, [tuple(p) for p in args["points"]], args.get("layer", ""))
    if name == "extrude_curve":
        return await geometry.extrude_curve(conn, args["profile_curve_id"], tuple(args["direction"]), args.get("cap", True), args.get("layer", ""))

    # ── Transform ─────────────────────────────────────────────────────────
    if name == "move_object":
        return await transform.move_object(conn, args["object_id"], tuple(args["translation"]), args.get("copy", False))
    if name == "rotate_object":
        return await transform.rotate_object(conn, args["object_id"], args["angle_degrees"], tuple(args.get("axis", [0, 0, 1])), tuple(args.get("center", [0, 0, 0])), args.get("copy", False))
    if name == "scale_object":
        s = args["scale"]
        scale_val = s if isinstance(s, (int, float)) else tuple(s)
        return await transform.scale_object(conn, args["object_id"], scale_val, tuple(args.get("center", [0, 0, 0])), args.get("copy", False))
    if name == "mirror_object":
        return await transform.mirror_object(conn, args["object_id"], tuple(args["mirror_plane_point1"]), tuple(args["mirror_plane_point2"]), args.get("copy", True))
    if name == "array_linear":
        return await transform.array_linear(conn, args["object_id"], args["count"], tuple(args["direction"]))
    if name == "array_polar":
        return await transform.array_polar(conn, args["object_id"], args["count"], tuple(args["center"]), tuple(args.get("axis", [0, 0, 1])))

    # ── Boolean ───────────────────────────────────────────────────────────
    if name == "boolean_difference":
        return await boolean.boolean_difference(conn, args["object_a"], args["objects_b"], args.get("delete_input", True))
    if name == "boolean_union":
        return await boolean.boolean_union(conn, args["object_ids"], args.get("delete_input", True))
    if name == "boolean_intersection":
        return await boolean.boolean_intersection(conn, args["object_ids"], args.get("delete_input", True))
    if name == "fillet_edges":
        return await boolean.fillet_edges(conn, args["object_id"], args.get("edge_indices"), args["radius"])

    # ── Surface ───────────────────────────────────────────────────────────
    if name == "loft":
        return await surface.loft(conn, args["curve_ids"], args.get("loft_type", 0), args.get("closed", False))
    if name == "sweep1":
        return await surface.sweep1(conn, args["rail_id"], args["profile_ids"], args.get("closed", False))
    if name == "sweep2":
        return await surface.sweep2(conn, args["rail1_id"], args["rail2_id"], args["profile_ids"], args.get("closed", False))
    if name == "revolve":
        return await surface.revolve(conn, args["profile_id"], tuple(args["axis_start"]), tuple(args["axis_end"]), args.get("start_angle", 0), args.get("end_angle", 360))
    if name == "pipe":
        return await surface.pipe(conn, args["rail_id"], args["radius"], args.get("cap_mode", 1))
    if name == "offset_surface":
        return await surface.offset_surface(conn, args["surface_id"], args["distance"], args.get("solid", False))

    # ── Selection ─────────────────────────────────────────────────────────
    if name == "select_by_layer":
        return await selection.select_by_layer(conn, args["layer_name"])
    if name == "select_by_type":
        return await selection.select_by_type(conn, args["object_type"])
    if name == "select_closest_to_point":
        return await selection.select_closest_to_point(conn, tuple(args["point"]), args.get("count", 1), args.get("object_type"))
    if name == "get_all_objects":
        return await selection.get_all_objects(conn)

    # ── Viewport ──────────────────────────────────────────────────────────
    if name == "capture_viewport":
        return await viewport.capture_viewport(conn, args.get("view_name", "Perspective"), args.get("width", 1280), args.get("height", 720), args.get("annotate_objects"))
    if name == "set_standard_view":
        return await viewport.set_standard_view(conn, args.get("view_name", "Perspective"), args.get("target_object_id"))
    if name == "zoom_to_object":
        return await viewport.zoom_to_object(conn, args["object_id"], args.get("view_name", "Perspective"))

    # ── Scene ─────────────────────────────────────────────────────────────
    if name == "get_scene_state":
        return await scene.get_scene_state(conn, args.get("include_geometry", False))
    if name == "get_object_info":
        return await scene.get_object_info(conn, args["object_id"])
    if name == "delete_objects":
        return await scene.delete_objects(conn, args["object_ids"])
    if name == "set_object_name":
        return await scene.set_object_name(conn, args["object_id"], args["name"])
    if name == "undo":
        return await scene.undo(conn, args.get("steps", 1))

    # ── Layers ────────────────────────────────────────────────────────────
    if name == "create_layer":
        return await layers.create_layer(conn, args["name"], tuple(args.get("color", [0, 0, 0])), args.get("parent", ""))
    if name == "set_object_layer":
        return await layers.set_object_layer(conn, args["object_id"], args["layer_name"])
    if name == "get_all_layers":
        return await layers.get_all_layers(conn)

    # ── Health ────────────────────────────────────────────────────────────
    if name == "health_check":
        req = RhinoRequest(type=MessageType.HEALTH_CHECK, payload={})
        resp = await conn.send_request(req)
        result = resp.model_dump()
        result["uptime_seconds"] = int(time.time() - _start_time)
        result["mock_mode"] = _mock_mode
        return result

    return {"status": "error", "error": {"type": "UnknownTool", "message": f"Unknown tool: {name}"}}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _run_server(mock: bool, host: str, port: int) -> None:
    global _connection, _mock_mode
    _mock_mode = mock

    if mock:
        _connection = MockRhinoConnection()
        logger.info("Starting RhinoMCP server in MOCK mode")
    else:
        _connection = RhinoConnection(host=host, port=port)
        logger.info(f"Starting RhinoMCP server, connecting to Rhino at {host}:{port}")
        try:
            await _connection.connect()
        except Exception as e:
            logger.error(f"Could not connect to Rhino: {e}. Falling back to mock mode.")
            _connection = MockRhinoConnection()
            _mock_mode = True

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="RhinoMCP Server")
    parser.add_argument("--mock", action="store_true", default=False, help="Run in mock mode (no Rhino needed)")
    parser.add_argument("--host", default=os.environ.get("RHINO_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("RHINO_PORT", "9876")))
    args = parser.parse_args()

    asyncio.run(_run_server(mock=args.mock, host=args.host, port=args.port))


if __name__ == "__main__":
    main()
