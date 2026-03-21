"""Boolean operation tools: union, difference, intersection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..protocol import MessageType, RhinoRequest

if TYPE_CHECKING:
    from ..connection import RhinoConnection
    from ..mock import MockRhinoConnection


def _build_code(code: str) -> str:
    return f"import rhinoscriptsyntax as rs\n{code}"


async def _exec(
    conn: "RhinoConnection | MockRhinoConnection",
    code: str,
    description: str,
    timeout: int = 60,
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


async def boolean_difference(
    conn: "RhinoConnection | MockRhinoConnection",
    object_a: str,
    objects_b: list[str],
    delete_input: bool = True,
    _mock_scenario: str = "",
) -> dict[str, Any]:
    """Subtract objects_b from object_a (Boolean Difference).

    Requirements:
    - All objects must be closed solids (watertight Breps).
    - object_a and objects_b must have geometric intersection.

    Args:
        object_a: GUID of the object to subtract FROM.
        objects_b: List of GUIDs of objects to subtract.
        delete_input: Delete input objects after operation (default True).
        _mock_scenario: Testing only — force a specific mock failure.
    """
    b_str = str(objects_b)
    code = (
        f'result = rs.BooleanDifference(["{object_a}"], {b_str}, delete_input={delete_input})\n'
        f"if result:\n"
        f"    print(result[0])\n"
        f"else:\n"
        f"    raise RuntimeError('BooleanDifference returned no result')\n"
    )
    extra: dict[str, Any] = {}
    if _mock_scenario:
        extra["_mock_scenario"] = _mock_scenario
        extra["object_a"] = object_a
    return await _exec(
        conn, code, f"BooleanDifference: {object_a} minus {objects_b}", extra_payload=extra
    )


async def boolean_union(
    conn: "RhinoConnection | MockRhinoConnection",
    object_ids: list[str],
    delete_input: bool = True,
) -> dict[str, Any]:
    """Join multiple closed solids into one (Boolean Union).

    Requirements:
    - All objects must be closed solids (watertight Breps).
    - Objects should overlap or touch.

    Args:
        object_ids: List of GUIDs to union.
        delete_input: Delete input objects after operation.
    """
    ids_str = str(object_ids)
    code = (
        f"result = rs.BooleanUnion({ids_str}, delete_input={delete_input})\n"
        f"if result:\n"
        f"    print(result[0])\n"
        f"else:\n"
        f"    raise RuntimeError('BooleanUnion returned no result')\n"
    )
    return await _exec(conn, code, f"BooleanUnion: {len(object_ids)} objects")


async def boolean_intersection(
    conn: "RhinoConnection | MockRhinoConnection",
    object_ids: list[str],
    delete_input: bool = True,
) -> dict[str, Any]:
    """Keep only the overlapping volume (Boolean Intersection).

    Requirements:
    - All objects must be closed solids.
    - Objects must intersect each other.

    Args:
        object_ids: List of GUIDs to intersect.
        delete_input: Delete input objects after operation.
    """
    ids_str = str(object_ids)
    code = (
        f"result = rs.BooleanIntersection({ids_str}, delete_input={delete_input})\n"
        f"if result:\n"
        f"    print(result[0])\n"
        f"else:\n"
        f"    raise RuntimeError('BooleanIntersection returned no result')\n"
    )
    return await _exec(conn, code, f"BooleanIntersection: {len(object_ids)} objects")


async def split_object(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    cutter_ids: list[str],
    delete_input: bool = True,
) -> dict[str, Any]:
    """Split an object using cutter curves or surfaces.

    Unlike Boolean operations, Split works on open surfaces too.

    Args:
        object_id: GUID of the object to split.
        cutter_ids: List of GUIDs used as cutting geometry.
        delete_input: Delete input after split.
    """
    cutters_str = str(cutter_ids)
    code = (
        f'result = rs.SplitBrep("{object_id}", {cutters_str}, delete_input={delete_input})\n'
        f"if result:\n"
        f"    print([str(r) for r in result])\n"
        f"else:\n"
        f"    raise RuntimeError('SplitBrep returned no result')\n"
    )
    return await _exec(conn, code, f"Split {object_id} with {len(cutter_ids)} cutters")


async def trim_surface(
    conn: "RhinoConnection | MockRhinoConnection",
    surface_id: str,
    cutter_ids: list[str],
    delete_input: bool = True,
) -> dict[str, Any]:
    """Trim a surface with cutting curves.

    Args:
        surface_id: GUID of the surface to trim.
        cutter_ids: GUIDs of curves/surfaces to trim with.
        delete_input: Delete input after trim.
    """
    cutters_str = str(cutter_ids)
    code = (
        f'result = rs.TrimBrep("{surface_id}", {cutters_str})\n'
        f"print(result)"
    )
    return await _exec(conn, code, f"Trim surface {surface_id}")


async def fillet_edges(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    edge_indices: list[int] | None,
    radius: float,
) -> dict[str, Any]:
    """Apply fillet (round) to edges of a solid.

    Args:
        object_id: GUID of the solid.
        edge_indices: List of edge indices to fillet, or None for all edges.
        radius: Fillet radius in mm.
    """
    if edge_indices is None:
        edges_code = f'edges = rs.SolidEdges("{object_id}")\nedge_ids = list(range(len(edges)))'
    else:
        edges_code = f"edge_ids = {edge_indices}"

    code = (
        f"{edges_code}\n"
        f'result = rs.FilletEdge("{object_id}", edge_ids, {radius})\n'
        f"print(result)"
    )
    return await _exec(conn, code, f"Fillet edges r={radius} on {object_id}")


async def chamfer_edges(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    edge_indices: list[int] | None,
    distance: float,
) -> dict[str, Any]:
    """Apply chamfer (bevel) to edges of a solid.

    Args:
        object_id: GUID of the solid.
        edge_indices: List of edge indices, or None for all edges.
        distance: Chamfer distance in mm.
    """
    if edge_indices is None:
        edges_code = f'edges = rs.SolidEdges("{object_id}")\nedge_ids = list(range(len(edges)))'
    else:
        edges_code = f"edge_ids = {edge_indices}"

    code = (
        f"{edges_code}\n"
        f'result = rs.ChamferEdge("{object_id}", edge_ids, {distance})\n'
        f"print(result)"
    )
    return await _exec(conn, code, f"Chamfer edges d={distance} on {object_id}")


async def shell_solid(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    thickness: float,
    face_indices_to_remove: list[int] | None = None,
) -> dict[str, Any]:
    """Shell (hollow out) a solid by offsetting all faces inward.

    Args:
        object_id: GUID of the solid.
        thickness: Shell wall thickness in mm.
        face_indices_to_remove: Face indices to open (leave as holes). None = all closed.
    """
    if face_indices_to_remove:
        faces_code = f"face_ids = {face_indices_to_remove}"
    else:
        faces_code = "face_ids = []"
    code = (
        f"{faces_code}\n"
        f'result = rs.ShellBrep("{object_id}", face_ids, {thickness})\n'
        f"print(result)"
    )
    return await _exec(conn, code, f"Shell solid t={thickness} on {object_id}")
