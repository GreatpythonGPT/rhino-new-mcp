"""Viewport and visual tools: capture screenshots, set views, annotations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..protocol import MessageType, RhinoRequest

if TYPE_CHECKING:
    from ..connection import RhinoConnection
    from ..mock import MockRhinoConnection

Point3d = tuple[float, float, float]

STANDARD_VIEWS = ("Top", "Front", "Right", "Perspective", "Back", "Left", "Bottom")


async def capture_viewport(
    conn: "RhinoConnection | MockRhinoConnection",
    view_name: str = "Perspective",
    width: int = 1280,
    height: int = 720,
    annotate_objects: list[str] | None = None,
) -> dict[str, Any]:
    """Capture a screenshot of the specified viewport.

    Args:
        view_name: Viewport name. Standard views: Top, Front, Right, Perspective.
        width: Image width in pixels.
        height: Image height in pixels.
        annotate_objects: List of object GUIDs to highlight with labels in the capture.

    Returns:
        Dict with image_path (local file) and optionally image_base64.
    """
    req = RhinoRequest(
        type=MessageType.CAPTURE_VIEWPORT,
        payload={
            "view_name": view_name,
            "width": width,
            "height": height,
            "annotate_objects": annotate_objects or [],
        },
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def set_standard_view(
    conn: "RhinoConnection | MockRhinoConnection",
    view_name: str = "Perspective",
    target_object_id: str | None = None,
) -> dict[str, Any]:
    """Switch to a standard view and optionally zoom to an object.

    Args:
        view_name: 'Top', 'Front', 'Right', 'Perspective', 'Back', 'Left', 'Bottom'.
        target_object_id: Optional GUID to zoom to.
    """
    code = f'rs.CurrentView("{view_name}")\n'
    if target_object_id:
        code += f'rs.ZoomObject("{target_object_id}")\n'
    code += "print('view set')"
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={
            "code": f"import rhinoscriptsyntax as rs\n{code}",
            "description": f"Set view to {view_name}",
        },
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def zoom_to_object(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    view_name: str = "Perspective",
) -> dict[str, Any]:
    """Zoom viewport to frame a specific object.

    Args:
        object_id: GUID of the object to zoom to.
        view_name: Which viewport to control.
    """
    code = (
        f'rs.CurrentView("{view_name}")\n'
        f'rs.ZoomObject("{object_id}")\n'
        f"print('zoomed')"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={
            "code": f"import rhinoscriptsyntax as rs\n{code}",
            "description": f"Zoom to {object_id}",
        },
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def zoom_to_all(
    conn: "RhinoConnection | MockRhinoConnection",
    view_name: str = "Perspective",
) -> dict[str, Any]:
    """Zoom viewport to show all objects.

    Args:
        view_name: Which viewport to control.
    """
    code = (
        f'rs.CurrentView("{view_name}")\n'
        f"rs.ZoomExtents()\n"
        f"print('zoomed to extents')"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={
            "code": f"import rhinoscriptsyntax as rs\n{code}",
            "description": "Zoom to extents",
        },
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def set_display_mode(
    conn: "RhinoConnection | MockRhinoConnection",
    mode: str = "Shaded",
    view_name: str = "Perspective",
) -> dict[str, Any]:
    """Change viewport display mode.

    Args:
        mode: Display mode name: 'Wireframe', 'Shaded', 'Rendered', 'Ghosted',
              'X-Ray', 'Technical', 'Pen', 'Artistic'.
        view_name: Which viewport to control.
    """
    code = (
        f'rs.CurrentView("{view_name}")\n'
        f'rs.ViewDisplayMode("{view_name}", "{mode}")\n'
        f"print('display mode set')"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={
            "code": f"import rhinoscriptsyntax as rs\n{code}",
            "description": f"Set display mode to {mode}",
        },
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def set_camera(
    conn: "RhinoConnection | MockRhinoConnection",
    camera_location: Point3d,
    camera_target: Point3d,
    view_name: str = "Perspective",
) -> dict[str, Any]:
    """Set the camera position and target for a perspective viewport.

    Args:
        camera_location: Camera eye position (x, y, z).
        camera_target: Camera look-at point (x, y, z).
        view_name: Viewport name (should be a perspective view).
    """
    code = (
        f'rs.CurrentView("{view_name}")\n'
        f'rs.ViewCamera("{view_name}", {list(camera_location)})\n'
        f'rs.ViewTarget("{view_name}", {list(camera_target)})\n'
        f"print('camera set')"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={
            "code": f"import rhinoscriptsyntax as rs\n{code}",
            "description": f"Set camera at {camera_location} looking at {camera_target}",
        },
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def add_clipping_plane(
    conn: "RhinoConnection | MockRhinoConnection",
    plane_origin: Point3d,
    plane_normal: Point3d = (0, 1, 0),
) -> dict[str, Any]:
    """Add a clipping plane for cross-section visualization.

    Args:
        plane_origin: A point on the clipping plane.
        plane_normal: Normal direction of the clipping plane.
    """
    code = (
        f"import Rhino.Geometry as rg\n"
        f"plane = rg.Plane(rg.Point3d(*{list(plane_origin)}), rg.Vector3d(*{list(plane_normal)}))\n"
        f"obj_id = rs.AddClippingPlane(plane, 100, 100)\n"
        f"print(obj_id)"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={
            "code": f"import rhinoscriptsyntax as rs\n{code}",
            "description": f"Add clipping plane at {plane_origin}",
        },
    )
    resp = await conn.send_request(req)
    return resp.model_dump()
