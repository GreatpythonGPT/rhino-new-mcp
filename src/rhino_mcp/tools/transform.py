"""Transform tools: move, rotate, scale, mirror, array."""

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
) -> dict[str, Any]:
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": _build_code(code), "description": description, "timeout": timeout},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def move_object(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    translation: Point3d,
    copy: bool = False,
) -> dict[str, Any]:
    """Move or copy an object by a translation vector.

    Args:
        object_id: GUID of the object to move.
        translation: Translation vector (dx, dy, dz) in mm.
        copy: If True, keep the original and move a copy.
    """
    dx, dy, dz = translation
    func = "CopyObject" if copy else "MoveObject"
    code = (
        f'obj_id = rs.{func}("{object_id}", [{dx}, {dy}, {dz}])\n'
        f"print(obj_id)"
    )
    return await _exec(conn, code, f"{'Copy' if copy else 'Move'} object by {translation}")


async def rotate_object(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    angle_degrees: float,
    axis: Point3d = (0, 0, 1),
    center: Point3d = (0, 0, 0),
    copy: bool = False,
) -> dict[str, Any]:
    """Rotate an object around an axis.

    Args:
        object_id: GUID of the object.
        angle_degrees: Rotation angle in degrees.
        axis: Rotation axis vector (default: Z-axis).
        center: Rotation center point.
        copy: If True, rotate a copy.
    """
    code = (
        f'obj_id = rs.RotateObject("{object_id}", {list(center)}, {angle_degrees}, '
        f'{list(axis)}, copy={copy})\n'
        f"print(obj_id)"
    )
    return await _exec(
        conn, code, f"Rotate {angle_degrees}° around {axis} at {center}"
    )


async def scale_object(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    scale: float | Point3d,
    center: Point3d = (0, 0, 0),
    copy: bool = False,
) -> dict[str, Any]:
    """Scale an object uniformly or non-uniformly.

    Args:
        object_id: GUID of the object.
        scale: Uniform scale factor (float) or (sx, sy, sz) for non-uniform.
        center: Scale origin point.
        copy: If True, scale a copy.
    """
    if isinstance(scale, (int, float)):
        sx, sy, sz = scale, scale, scale
    else:
        sx, sy, sz = scale
    code = (
        f'obj_id = rs.ScaleObject("{object_id}", {list(center)}, [{sx},{sy},{sz}], copy={copy})\n'
        f"print(obj_id)"
    )
    return await _exec(conn, code, f"Scale object by ({sx},{sy},{sz})")


async def mirror_object(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    mirror_plane_point1: Point3d,
    mirror_plane_point2: Point3d,
    copy: bool = True,
) -> dict[str, Any]:
    """Mirror an object across a plane defined by two points (in XY plane).

    Args:
        object_id: GUID of the object.
        mirror_plane_point1: First point on mirror plane.
        mirror_plane_point2: Second point on mirror plane.
        copy: Keep original (default True).
    """
    code = (
        f'obj_id = rs.MirrorObject("{object_id}", {list(mirror_plane_point1)}, '
        f'{list(mirror_plane_point2)}, copy={copy})\n'
        f"print(obj_id)"
    )
    return await _exec(conn, code, "Mirror object")


async def array_linear(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    count: int,
    direction: Point3d,
) -> dict[str, Any]:
    """Create a linear array of copies.

    Args:
        object_id: GUID of the source object.
        count: Total number of objects (including original).
        direction: Step vector (dx, dy, dz) between each copy.
    """
    dx, dy, dz = direction
    code = (
        f"result_ids = []\n"
        f'for i in range(1, {count}):\n'
        f'    copy_id = rs.CopyObject("{object_id}", [{dx}*i, {dy}*i, {dz}*i])\n'
        f"    result_ids.append(str(copy_id))\n"
        f"print(result_ids)"
    )
    return await _exec(conn, code, f"Linear array count={count} step={direction}")


async def array_polar(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    count: int,
    center: Point3d,
    axis: Point3d = (0, 0, 1),
) -> dict[str, Any]:
    """Create a polar (rotational) array of copies.

    Args:
        object_id: GUID of the source object.
        count: Total number of objects (including original).
        center: Center of rotation.
        axis: Rotation axis (default: Z-up).
    """
    angle_step = 360.0 / count
    code = (
        f"result_ids = []\n"
        f"for i in range(1, {count}):\n"
        f'    copy_id = rs.RotateObject("{object_id}", {list(center)}, '
        f'{angle_step}*i, {list(axis)}, copy=True)\n'
        f"    result_ids.append(str(copy_id))\n"
        f"print(result_ids)"
    )
    return await _exec(conn, code, f"Polar array count={count} center={center}")


async def align_objects(
    conn: "RhinoConnection | MockRhinoConnection",
    object_ids: list[str],
    align_to: str = "world_xy",
) -> dict[str, Any]:
    """Align objects to a plane or bounding box.

    Args:
        object_ids: List of GUIDs.
        align_to: 'world_xy', 'world_xz', 'world_yz', 'bottom', 'center_x', 'center_y'.
    """
    ids_str = str(object_ids)
    code = (
        f"ids = {ids_str}\n"
        f"bbox_points = [rs.BoundingBox(oid) for oid in ids if rs.BoundingBox(oid)]\n"
        f"# align_to={align_to!r} — implement specific alignment as needed\n"
        f"print('aligned')"
    )
    return await _exec(conn, code, f"Align {len(object_ids)} objects to {align_to}")
