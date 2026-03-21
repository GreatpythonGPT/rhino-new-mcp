"""Geometry creation tools: primitives and basic shapes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..protocol import MessageType, RhinoRequest

if TYPE_CHECKING:
    from ..connection import RhinoConnection
    from ..mock import MockRhinoConnection

Point3d = tuple[float, float, float]


def _build_code(code: str) -> str:
    """Wrap code with standard rhinoscriptsyntax import."""
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


async def create_sphere(
    conn: "RhinoConnection | MockRhinoConnection",
    center: Point3d,
    radius: float,
    layer: str = "",
) -> dict[str, Any]:
    """Create a sphere.

    Args:
        center: Center point (x, y, z) in mm.
        radius: Radius in mm.
        layer: Optional layer name.
    """
    code = f"obj_id = rs.AddSphere({list(center)}, {radius})\n"
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Create sphere r={radius} at {center}")


async def create_box(
    conn: "RhinoConnection | MockRhinoConnection",
    corner: Point3d,
    width: float,
    depth: float,
    height: float,
    layer: str = "",
) -> dict[str, Any]:
    """Create a box (rectangular solid).

    Args:
        corner: Base corner point (x, y, z).
        width: Size along X axis in mm.
        depth: Size along Y axis in mm.
        height: Size along Z axis in mm.
        layer: Optional layer name.
    """
    x, y, z = corner
    code = (
        f"corners = [\n"
        f"    [{x}, {y}, {z}],\n"
        f"    [{x + width}, {y}, {z}],\n"
        f"    [{x + width}, {y + depth}, {z}],\n"
        f"    [{x}, {y + depth}, {z}],\n"
        f"    [{x}, {y}, {z + height}],\n"
        f"    [{x + width}, {y}, {z + height}],\n"
        f"    [{x + width}, {y + depth}, {z + height}],\n"
        f"    [{x}, {y + depth}, {z + height}],\n"
        f"]\n"
        f"obj_id = rs.AddBox(corners)\n"
    )
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Create box {width}x{depth}x{height} at {corner}")


async def create_cylinder(
    conn: "RhinoConnection | MockRhinoConnection",
    base_center: Point3d,
    height: float,
    radius: float,
    layer: str = "",
) -> dict[str, Any]:
    """Create a vertical cylinder.

    Args:
        base_center: Center of the base circle (x, y, z).
        height: Height in mm (positive = upward).
        radius: Radius in mm.
        layer: Optional layer name.
    """
    x, y, z = base_center
    code = (
        f"base_plane = rs.WorldXYPlane()\n"
        f"base_plane = rs.MovePlane(base_plane, [{x}, {y}, {z}])\n"
        f"circle = rs.AddCircle(base_plane, {radius})\n"
        f"obj_id = rs.ExtrudeCurve(circle, rs.AddLine([{x},{y},{z}],[{x},{y},{z+height}]))\n"
        f"rs.CapPlanarHoles(obj_id)\n"
        f"rs.DeleteObject(circle)\n"
    )
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Create cylinder r={radius} h={height} at {base_center}")


async def create_cone(
    conn: "RhinoConnection | MockRhinoConnection",
    base_center: Point3d,
    height: float,
    radius: float,
    layer: str = "",
) -> dict[str, Any]:
    """Create a cone (base circle up to apex).

    Args:
        base_center: Center of the base circle.
        height: Height of the cone.
        radius: Base radius.
        layer: Optional layer name.
    """
    x, y, z = base_center
    code = (
        f"base_plane = rs.WorldXYPlane()\n"
        f"base_plane = rs.MovePlane(base_plane, [{x}, {y}, {z}])\n"
        f"obj_id = rs.AddCone(base_plane, {height}, {radius})\n"
    )
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Create cone r={radius} h={height} at {base_center}")


async def create_torus(
    conn: "RhinoConnection | MockRhinoConnection",
    center: Point3d,
    major_radius: float,
    minor_radius: float,
    layer: str = "",
) -> dict[str, Any]:
    """Create a torus (donut shape).

    Args:
        center: Center of the torus.
        major_radius: Outer radius (from center to tube center).
        minor_radius: Tube radius.
        layer: Optional layer name.
    """
    x, y, z = center
    code = (
        f"plane = rs.WorldXYPlane()\n"
        f"plane = rs.MovePlane(plane, [{x}, {y}, {z}])\n"
        f"obj_id = rs.AddTorus(plane, {major_radius}, {minor_radius})\n"
    )
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(
        conn, code, f"Create torus R={major_radius} r={minor_radius} at {center}"
    )


async def create_line(
    conn: "RhinoConnection | MockRhinoConnection",
    start: Point3d,
    end: Point3d,
    layer: str = "",
) -> dict[str, Any]:
    """Create a line curve between two points."""
    code = f"obj_id = rs.AddLine({list(start)}, {list(end)})\n"
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Create line {start} -> {end}")


async def create_circle(
    conn: "RhinoConnection | MockRhinoConnection",
    center: Point3d,
    radius: float,
    normal: Point3d = (0, 0, 1),
    layer: str = "",
) -> dict[str, Any]:
    """Create a circle curve.

    Args:
        center: Center point.
        radius: Radius in mm.
        normal: Normal direction of the circle plane (default: Z-up).
        layer: Optional layer name.
    """
    code = (
        f"import Rhino.Geometry as rg\n"
        f"plane = rg.Plane(rg.Point3d(*{list(center)}), rg.Vector3d(*{list(normal)}))\n"
        f"circle = rg.Circle(plane, {radius})\n"
        f"obj_id = rs.AddCircle(plane, {radius})\n"
    )
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Create circle r={radius} at {center}")


async def create_rectangle(
    conn: "RhinoConnection | MockRhinoConnection",
    corner: Point3d,
    width: float,
    height: float,
    layer: str = "",
) -> dict[str, Any]:
    """Create a rectangle curve in the XY plane."""
    x, y, z = corner
    code = (
        f"plane = rs.WorldXYPlane()\n"
        f"plane = rs.MovePlane(plane, [{x}, {y}, {z}])\n"
        f"obj_id = rs.AddRectangle(plane, {width}, {height})\n"
    )
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Create rectangle {width}x{height} at {corner}")


async def create_polyline(
    conn: "RhinoConnection | MockRhinoConnection",
    points: list[Point3d],
    layer: str = "",
) -> dict[str, Any]:
    """Create a polyline through a list of points."""
    pts_str = str([list(p) for p in points])
    code = f"obj_id = rs.AddPolyline({pts_str})\n"
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Create polyline with {len(points)} points")


async def create_nurbs_curve(
    conn: "RhinoConnection | MockRhinoConnection",
    points: list[Point3d],
    degree: int = 3,
    layer: str = "",
) -> dict[str, Any]:
    """Create a smooth NURBS curve through control points.

    Args:
        points: Control points.
        degree: Curve degree (1=linear, 2=quadratic, 3=cubic).
        layer: Optional layer name.
    """
    pts_str = str([list(p) for p in points])
    code = f"obj_id = rs.AddCurve({pts_str}, {degree})\n"
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Create NURBS curve degree={degree}")


async def create_planar_surface(
    conn: "RhinoConnection | MockRhinoConnection",
    boundary_curve_id: str,
    layer: str = "",
) -> dict[str, Any]:
    """Create a planar surface from a closed planar curve.

    Args:
        boundary_curve_id: GUID of a closed planar curve.
        layer: Optional layer name.
    """
    code = (
        f'objs = rs.AddPlanarSrf(["{boundary_curve_id}"])\n'
        f"obj_id = objs[0] if objs else None\n"
    )
    if layer:
        code += f'if obj_id: rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, "Create planar surface from curve")


async def extrude_curve(
    conn: "RhinoConnection | MockRhinoConnection",
    profile_curve_id: str,
    direction: Point3d,
    cap: bool = True,
    layer: str = "",
) -> dict[str, Any]:
    """Extrude a curve along a direction vector.

    Args:
        profile_curve_id: GUID of the profile curve.
        direction: Extrusion direction vector (x, y, z) — length = extrusion distance.
        cap: Whether to cap the ends (makes it a closed solid if profile is closed).
        layer: Optional layer name.
    """
    dx, dy, dz = direction
    code = (
        f'path = rs.AddLine([0,0,0], [{dx},{dy},{dz}])\n'
        f'obj_id = rs.ExtrudeCurve("{profile_curve_id}", path)\n'
        f"rs.DeleteObject(path)\n"
    )
    if cap:
        code += "rs.CapPlanarHoles(obj_id)\n"
    if layer:
        code += f'rs.ObjectLayer(obj_id, "{layer}")\n'
    code += "print(obj_id)"
    return await _exec(conn, code, f"Extrude curve along {direction}")
