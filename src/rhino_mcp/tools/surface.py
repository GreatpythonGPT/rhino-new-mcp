"""Surface modeling tools: Loft, Sweep, Revolve, Offset, Pipe, etc."""

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
    timeout: int = 60,
) -> dict[str, Any]:
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": _build_code(code), "description": description, "timeout": timeout},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def loft(
    conn: "RhinoConnection | MockRhinoConnection",
    curve_ids: list[str],
    loft_type: int = 0,
    closed: bool = False,
) -> dict[str, Any]:
    """Create a lofted surface through a series of cross-section curves.

    Requirements:
    - Curves should be sorted in the order to loft through.
    - All curves should have compatible direction (use rs.CurveSeam to adjust).

    Args:
        curve_ids: Ordered list of cross-section curve GUIDs.
        loft_type: 0=Normal, 1=Loose, 2=Tight, 3=Straight, 4=Developable.
        closed: Create a closed (periodic) loft.
    """
    ids_str = str(curve_ids)
    code = (
        f"result = rs.AddLoftSrf({ids_str}, loft_type={loft_type}, closed={closed})\n"
        f"if result:\n"
        f"    print(result[0])\n"
        f"else:\n"
        f"    raise RuntimeError('Loft failed')\n"
    )
    return await _exec(conn, code, f"Loft {len(curve_ids)} curves type={loft_type}")


async def sweep1(
    conn: "RhinoConnection | MockRhinoConnection",
    rail_id: str,
    profile_ids: list[str],
    closed: bool = False,
) -> dict[str, Any]:
    """Create a sweep surface along a single rail curve.

    Args:
        rail_id: GUID of the rail (path) curve.
        profile_ids: List of GUIDs of cross-section profile curves.
        closed: Close the sweep at the rail ends.
    """
    profiles_str = str(profile_ids)
    code = (
        f'result = rs.AddSweep1("{rail_id}", {profiles_str}, closed={closed})\n'
        f"if result:\n"
        f"    print(result[0])\n"
        f"else:\n"
        f"    raise RuntimeError('Sweep1 failed')\n"
    )
    return await _exec(conn, code, f"Sweep1: rail={rail_id} profiles={profile_ids}")


async def sweep2(
    conn: "RhinoConnection | MockRhinoConnection",
    rail1_id: str,
    rail2_id: str,
    profile_ids: list[str],
    closed: bool = False,
) -> dict[str, Any]:
    """Create a sweep surface along two rail curves.

    Args:
        rail1_id: GUID of first rail curve.
        rail2_id: GUID of second rail curve.
        profile_ids: List of GUIDs of cross-section profiles.
        closed: Close the sweep.
    """
    profiles_str = str(profile_ids)
    code = (
        f'result = rs.AddSweep2("{rail1_id}", "{rail2_id}", {profiles_str}, closed={closed})\n'
        f"if result:\n"
        f"    print(result[0])\n"
        f"else:\n"
        f"    raise RuntimeError('Sweep2 failed')\n"
    )
    return await _exec(conn, code, f"Sweep2 with 2 rails and {len(profile_ids)} profiles")


async def revolve(
    conn: "RhinoConnection | MockRhinoConnection",
    profile_id: str,
    axis_start: Point3d,
    axis_end: Point3d,
    start_angle: float = 0,
    end_angle: float = 360,
) -> dict[str, Any]:
    """Revolve a profile curve around an axis.

    Args:
        profile_id: GUID of the profile curve to revolve.
        axis_start: Start point of rotation axis.
        axis_end: End point of rotation axis.
        start_angle: Start angle in degrees (default 0).
        end_angle: End angle in degrees (default 360 = full revolution).
    """
    code = (
        f'result = rs.AddRevSrf("{profile_id}", ({list(axis_start)}, {list(axis_end)}), '
        f'{start_angle}, {end_angle})\n'
        f"if result:\n"
        f"    print(result)\n"
        f"else:\n"
        f"    raise RuntimeError('Revolve failed')\n"
    )
    return await _exec(
        conn, code, f"Revolve {profile_id} {start_angle}-{end_angle}° around axis"
    )


async def pipe(
    conn: "RhinoConnection | MockRhinoConnection",
    rail_id: str,
    radius: float | list[float],
    cap_mode: int = 1,
) -> dict[str, Any]:
    """Create a pipe along a rail curve.

    Args:
        rail_id: GUID of the centerline curve.
        radius: Pipe radius (uniform float or list for variable radius).
        cap_mode: 0=None, 1=Flat, 2=Round.
    """
    if isinstance(radius, (int, float)):
        radii = [radius]
        params = [0.0]
    else:
        radii = list(radius)
        params = [i / (len(radii) - 1) for i in range(len(radii))] if len(radii) > 1 else [0.0]

    code = (
        f'result = rs.AddPipe("{rail_id}", {params}, {radii}, cap={cap_mode})\n'
        f"if result:\n"
        f"    print(result[0])\n"
        f"else:\n"
        f"    raise RuntimeError('Pipe failed')\n"
    )
    return await _exec(conn, code, f"Pipe along {rail_id} r={radius}")


async def offset_surface(
    conn: "RhinoConnection | MockRhinoConnection",
    surface_id: str,
    distance: float,
    solid: bool = False,
) -> dict[str, Any]:
    """Offset a surface or solid by a distance.

    Args:
        surface_id: GUID of the surface or solid to offset.
        distance: Offset distance in mm (positive = outward, negative = inward).
        solid: Create a solid between original and offset.
    """
    code = (
        f'result = rs.OffsetSurface("{surface_id}", {distance}, solid={solid})\n'
        f"print(result)"
    )
    return await _exec(conn, code, f"Offset surface d={distance}")


async def offset_curve(
    conn: "RhinoConnection | MockRhinoConnection",
    curve_id: str,
    distance: float,
    normal: Point3d = (0, 0, 1),
) -> dict[str, Any]:
    """Offset a curve by a distance in a plane.

    Args:
        curve_id: GUID of the curve to offset.
        distance: Offset distance in mm.
        normal: Normal vector of the offset plane.
    """
    code = (
        f'result = rs.OffsetCurve("{curve_id}", {list(normal)}, {distance})\n'
        f"print(result)"
    )
    return await _exec(conn, code, f"Offset curve d={distance}")


async def flow_along_surface(
    conn: "RhinoConnection | MockRhinoConnection",
    object_ids: list[str],
    source_surface_id: str,
    target_surface_id: str,
    copy: bool = True,
) -> dict[str, Any]:
    """Flow/morph objects from a source surface to a target surface.

    Useful for applying patterns to curved surfaces.

    Args:
        object_ids: GUIDs of objects to flow.
        source_surface_id: GUID of the base (flat) surface.
        target_surface_id: GUID of the target curved surface.
        copy: Keep originals.
    """
    ids_str = str(object_ids)
    code = (
        f'result = rs.FlowAlongSrf({ids_str}, "{source_surface_id}", '
        f'"{target_surface_id}", copy={copy})\n'
        f"print(result)"
    )
    return await _exec(conn, code, f"Flow {len(object_ids)} objects along surface")


async def rebuild_surface(
    conn: "RhinoConnection | MockRhinoConnection",
    surface_id: str,
    u_degree: int = 3,
    v_degree: int = 3,
    u_points: int = 10,
    v_points: int = 10,
) -> dict[str, Any]:
    """Rebuild a surface with new point count and degree.

    Useful for cleaning up complex surfaces or adding control points.

    Args:
        surface_id: GUID of the surface to rebuild.
        u_degree: Degree in U direction.
        v_degree: Degree in V direction.
        u_points: Control point count in U direction.
        v_points: Control point count in V direction.
    """
    code = (
        f'result = rs.RebuildSurface("{surface_id}", ({u_degree}, {v_degree}), '
        f'({u_points}, {v_points}))\n'
        f"print(result)"
    )
    return await _exec(conn, code, f"Rebuild surface {surface_id}")


async def join_surfaces(
    conn: "RhinoConnection | MockRhinoConnection",
    surface_ids: list[str],
    delete_input: bool = True,
) -> dict[str, Any]:
    """Join multiple surfaces into a polysurface.

    Args:
        surface_ids: List of surface GUIDs.
        delete_input: Delete originals after join.
    """
    ids_str = str(surface_ids)
    code = (
        f"result = rs.JoinSurfaces({ids_str}, delete_input={delete_input})\n"
        f"print(result)"
    )
    return await _exec(conn, code, f"Join {len(surface_ids)} surfaces")


async def cap_holes(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
) -> dict[str, Any]:
    """Cap planar holes in an open polysurface to make it a solid.

    Args:
        object_id: GUID of the open polysurface.
    """
    code = (
        f'result = rs.CapPlanarHoles("{object_id}")\n'
        f"print(result)"
    )
    return await _exec(conn, code, f"Cap holes on {object_id}")
