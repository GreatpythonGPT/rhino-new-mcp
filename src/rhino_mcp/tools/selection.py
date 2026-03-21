"""Selection tools: semantic and geometric object selection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..protocol import MessageType, RhinoRequest

if TYPE_CHECKING:
    from ..connection import RhinoConnection
    from ..mock import MockRhinoConnection

Point3d = tuple[float, float, float]


def _build_code(code: str) -> str:
    return f"import rhinoscriptsyntax as rs\n{code}"


async def _exec(
    conn: "RhinoConnection | MockRhinoConnection",
    code: str,
    description: str,
    timeout: int = 30,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": _build_code(code),
        "description": description,
        "timeout": timeout,
    }
    if extra_payload:
        payload.update(extra_payload)
    req = RhinoRequest(type=MessageType.EXECUTE_COMMAND, payload=payload)
    resp = await conn.send_request(req)
    return resp.model_dump()


async def select_by_layer(
    conn: "RhinoConnection | MockRhinoConnection",
    layer_name: str,
) -> dict[str, Any]:
    """Get all object GUIDs on a specific layer.

    Args:
        layer_name: Exact layer name.
    """
    req = RhinoRequest(
        type=MessageType.SELECT_OBJECTS,
        payload={"filter_layer": layer_name},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def select_by_type(
    conn: "RhinoConnection | MockRhinoConnection",
    object_type: str,
) -> dict[str, Any]:
    """Get all object GUIDs matching a type.

    Args:
        object_type: One of: curve, surface, brep, mesh, point, light, annotation.
    """
    req = RhinoRequest(
        type=MessageType.SELECT_OBJECTS,
        payload={"filter_type": object_type},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def select_by_bounding_box(
    conn: "RhinoConnection | MockRhinoConnection",
    min_point: Point3d,
    max_point: Point3d,
) -> dict[str, Any]:
    """Get all object GUIDs whose bounding box overlaps with the given box.

    Args:
        min_point: Minimum corner (x, y, z) of selection box.
        max_point: Maximum corner (x, y, z) of selection box.
    """
    code = (
        f"import Rhino\n"
        f"import Rhino.Geometry as rg\n"
        f"bbox = rg.BoundingBox(rg.Point3d(*{list(min_point)}), rg.Point3d(*{list(max_point)}))\n"
        f"selected = []\n"
        f"for obj in Rhino.RhinoDoc.ActiveDoc.Objects:\n"
        f"    if not obj.IsDeleted and obj.Geometry.GetBoundingBox(True).IsValid:\n"
        f"        obj_bb = obj.Geometry.GetBoundingBox(True)\n"
        f"        if rg.BoundingBox.Intersection(bbox, obj_bb).IsValid:\n"
        f"            selected.append(str(obj.Id))\n"
        f"print(selected)\n"
    )
    return await _exec(
        conn, code, f"Select objects in bbox {min_point} to {max_point}", timeout=15
    )


async def select_closest_to_point(
    conn: "RhinoConnection | MockRhinoConnection",
    point: Point3d,
    count: int = 1,
    object_type: str | None = None,
) -> dict[str, Any]:
    """Find the closest N objects to a point.

    Args:
        point: Reference point (x, y, z).
        count: Number of closest objects to return.
        object_type: Optional type filter.
    """
    type_filter = f'rs.filter.{object_type}' if object_type else 'rs.filter.object'
    code = (
        f"import Rhino\n"
        f"import Rhino.Geometry as rg\n"
        f"ref_pt = rg.Point3d(*{list(point)})\n"
        f"objs_with_dist = []\n"
        f"for obj in Rhino.RhinoDoc.ActiveDoc.Objects:\n"
        f"    if obj.IsDeleted: continue\n"
        f"    bb = obj.Geometry.GetBoundingBox(True)\n"
        f"    if bb.IsValid:\n"
        f"        dist = ref_pt.DistanceTo(bb.Center)\n"
        f"        objs_with_dist.append((dist, str(obj.Id)))\n"
        f"objs_with_dist.sort(key=lambda x: x[0])\n"
        f"result = [oid for _, oid in objs_with_dist[:{count}]]\n"
        f"print(result)\n"
    )
    return await _exec(conn, code, f"Select {count} closest objects to {point}")


async def select_topmost_objects(
    conn: "RhinoConnection | MockRhinoConnection",
    count: int = 1,
    axis: str = "z",
) -> dict[str, Any]:
    """Find objects with the highest position along an axis.

    Args:
        count: Number of objects to return.
        axis: 'x', 'y', or 'z'.
    """
    axis_index = {"x": 0, "y": 1, "z": 2}.get(axis.lower(), 2)
    code = (
        f"import Rhino\n"
        f"objs_with_pos = []\n"
        f"for obj in Rhino.RhinoDoc.ActiveDoc.Objects:\n"
        f"    if obj.IsDeleted: continue\n"
        f"    bb = obj.Geometry.GetBoundingBox(True)\n"
        f"    if bb.IsValid:\n"
        f"        pos = bb.Max[{axis_index}]\n"
        f"        objs_with_pos.append((pos, str(obj.Id)))\n"
        f"objs_with_pos.sort(key=lambda x: x[0], reverse=True)\n"
        f"result = [oid for _, oid in objs_with_pos[:{count}]]\n"
        f"print(result)\n"
    )
    return await _exec(conn, code, f"Select {count} topmost objects along {axis}-axis")


async def select_by_name(
    conn: "RhinoConnection | MockRhinoConnection",
    name: str,
) -> dict[str, Any]:
    """Find objects by their user-assigned name.

    Args:
        name: Object name (exact match).
    """
    code = (
        f'obj_ids = rs.ObjectsByName("{name}")\n'
        f"print([str(oid) for oid in obj_ids] if obj_ids else [])\n"
    )
    return await _exec(conn, code, f"Select objects named '{name}'")


async def get_all_objects(
    conn: "RhinoConnection | MockRhinoConnection",
) -> dict[str, Any]:
    """Get a list of all objects in the document.

    Returns a dict with object GUIDs, types, layers, and names.
    """
    req = RhinoRequest(
        type=MessageType.QUERY_STATE,
        payload={"include_geometry": False},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()
