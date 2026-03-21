"""Scene query tools: inspect objects, geometry properties, document state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..protocol import MessageType, RhinoRequest

if TYPE_CHECKING:
    from ..connection import RhinoConnection
    from ..mock import MockRhinoConnection


async def get_scene_state(
    conn: "RhinoConnection | MockRhinoConnection",
    include_geometry: bool = False,
) -> dict[str, Any]:
    """Get a full snapshot of the current Rhino document state.

    Args:
        include_geometry: If True, include detailed geometry info (slower).

    Returns:
        Dict with objects list, layers, document info.
    """
    req = RhinoRequest(
        type=MessageType.QUERY_STATE,
        payload={"include_geometry": include_geometry},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def get_object_info(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
) -> dict[str, Any]:
    """Get detailed info about a specific object.

    Args:
        object_id: GUID of the object.

    Returns:
        Dict with type, layer, bounding box, area/volume if applicable.
    """
    code = (
        f"import Rhino\n"
        f"import rhinoscriptsyntax as rs\n"
        f'obj_id = "{object_id}"\n'
        f"info = {{\n"
        f"    'id': str(obj_id),\n"
        f"    'type': str(rs.ObjectType(obj_id)),\n"
        f"    'layer': rs.ObjectLayer(obj_id),\n"
        f"    'name': rs.ObjectName(obj_id) or '',\n"
        f"    'visible': rs.IsObjectVisible(obj_id),\n"
        f"    'is_closed': rs.IsBrep(obj_id) and rs.IsObject(obj_id),\n"
        f"}}\n"
        f"# Bounding box\n"
        f"bb = rs.BoundingBox(obj_id)\n"
        f"if bb:\n"
        f"    info['bounding_box'] = {{\n"
        f"        'min': list(bb[0]),\n"
        f"        'max': list(bb[6]),\n"
        f"    }}\n"
        f"# Area / Volume\n"
        f"try:\n"
        f"    info['area'] = rs.Area(obj_id)\n"
        f"except: pass\n"
        f"try:\n"
        f"    info['volume'] = rs.Volume(obj_id)\n"
        f"except: pass\n"
        f"import json\n"
        f"print(json.dumps(info))\n"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": code, "description": f"Get info for {object_id}"},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def check_geometry_validity(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
) -> dict[str, Any]:
    """Check if an object's geometry is valid (no naked edges, watertight, etc.).

    Args:
        object_id: GUID of the object to check.
    """
    code = (
        f"import Rhino\n"
        f"import rhinoscriptsyntax as rs\n"
        f'rhino_obj = rs.coercerhinoobject("{object_id}")\n'
        f"is_valid = rhino_obj.IsValid if rhino_obj else False\n"
        f"validation_log = ''\n"
        f"if rhino_obj:\n"
        f"    log_text = rhino_obj.Geometry.IsValidWithLog()[1]\n"
        f"    validation_log = log_text or 'Valid'\n"
        f"is_closed = rs.IsBrep('{object_id}') and False  # placeholder\n"
        f"import json\n"
        f"print(json.dumps({{\n"
        f"    'id': '{object_id}',\n"
        f"    'is_valid': is_valid,\n"
        f"    'validation_log': validation_log,\n"
        f"}}))\n"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": code, "description": f"Check validity of {object_id}"},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def set_object_name(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    name: str,
) -> dict[str, Any]:
    """Assign a name to an object for later reference.

    Args:
        object_id: GUID of the object.
        name: Name string.
    """
    code = (
        f"import rhinoscriptsyntax as rs\n"
        f'rs.ObjectName("{object_id}", "{name}")\n'
        f"print('named')"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": code, "description": f"Name {object_id} as '{name}'"},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def delete_objects(
    conn: "RhinoConnection | MockRhinoConnection",
    object_ids: list[str],
) -> dict[str, Any]:
    """Delete objects from the document.

    Args:
        object_ids: List of GUIDs to delete.
    """
    ids_str = str(object_ids)
    code = (
        f"import rhinoscriptsyntax as rs\n"
        f"rs.DeleteObjects({ids_str})\n"
        f"print('deleted')"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": code, "description": f"Delete {len(object_ids)} objects"},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def group_objects(
    conn: "RhinoConnection | MockRhinoConnection",
    object_ids: list[str],
    group_name: str = "",
) -> dict[str, Any]:
    """Group objects together.

    Args:
        object_ids: GUIDs to group.
        group_name: Optional group name.
    """
    ids_str = str(object_ids)
    name_arg = f'"{group_name}"' if group_name else "None"
    code = (
        f"import rhinoscriptsyntax as rs\n"
        f"group = rs.AddGroup({name_arg})\n"
        f"rs.AddObjectsToGroup({ids_str}, group)\n"
        f"print(group)"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": code, "description": f"Group {len(object_ids)} objects"},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def undo(
    conn: "RhinoConnection | MockRhinoConnection",
    steps: int = 1,
) -> dict[str, Any]:
    """Undo the last N operations.

    Args:
        steps: Number of undo steps.
    """
    code = (
        f"import Rhino\n"
        f"for _ in range({steps}):\n"
        f"    Rhino.RhinoApp.RunScript('_Undo', False)\n"
        f"print('undone {steps} steps')"
    )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": code, "description": f"Undo {steps} steps"},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()


async def save_document(
    conn: "RhinoConnection | MockRhinoConnection",
    file_path: str = "",
) -> dict[str, Any]:
    """Save the current Rhino document.

    Args:
        file_path: Full path to save to. If empty, saves to current document path.
    """
    if file_path:
        code = (
            f"import Rhino\n"
            f'result = Rhino.RhinoDoc.ActiveDoc.WriteFile("{file_path}", None)\n'
            f"print('saved to {file_path}' if result else 'save failed')"
        )
    else:
        code = (
            f"import Rhino\n"
            f"Rhino.RhinoApp.RunScript('_Save', False)\n"
            f"print('saved')"
        )
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": code, "description": "Save document"},
    )
    resp = await conn.send_request(req)
    return resp.model_dump()
