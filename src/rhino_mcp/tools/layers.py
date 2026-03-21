"""Layer management tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..protocol import MessageType, RhinoRequest

if TYPE_CHECKING:
    from ..connection import RhinoConnection
    from ..mock import MockRhinoConnection


def _exec_code(code: str, description: str) -> RhinoRequest:
    return RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={
            "code": f"import rhinoscriptsyntax as rs\n{code}",
            "description": description,
        },
    )


async def create_layer(
    conn: "RhinoConnection | MockRhinoConnection",
    name: str,
    color: tuple[int, int, int] = (0, 0, 0),
    parent: str = "",
) -> dict[str, Any]:
    """Create a new layer.

    Args:
        name: Layer name (use '::' for sub-layers, e.g. 'Structure::Walls').
        color: RGB color tuple (0-255 each).
        parent: Parent layer name for nested layers.
    """
    r, g, b = color
    parent_arg = f'"{parent}"' if parent else "None"
    code = (
        f'layer = rs.AddLayer("{name}", ({r},{g},{b}), parent_name={parent_arg})\n'
        f"print(layer)"
    )
    resp = await conn.send_request(_exec_code(code, f"Create layer '{name}'"))
    return resp.model_dump()


async def set_object_layer(
    conn: "RhinoConnection | MockRhinoConnection",
    object_id: str,
    layer_name: str,
) -> dict[str, Any]:
    """Move an object to a specific layer.

    Args:
        object_id: GUID of the object.
        layer_name: Target layer name.
    """
    code = f'rs.ObjectLayer("{object_id}", "{layer_name}")\nprint("moved")'
    resp = await conn.send_request(
        _exec_code(code, f"Move {object_id} to layer '{layer_name}'")
    )
    return resp.model_dump()


async def set_layer_visibility(
    conn: "RhinoConnection | MockRhinoConnection",
    layer_name: str,
    visible: bool,
) -> dict[str, Any]:
    """Show or hide a layer.

    Args:
        layer_name: Layer to control.
        visible: True to show, False to hide.
    """
    code = f'rs.LayerVisible("{layer_name}", {visible})\nprint("visibility set")'
    resp = await conn.send_request(
        _exec_code(code, f"{'Show' if visible else 'Hide'} layer '{layer_name}'")
    )
    return resp.model_dump()


async def set_layer_lock(
    conn: "RhinoConnection | MockRhinoConnection",
    layer_name: str,
    locked: bool,
) -> dict[str, Any]:
    """Lock or unlock a layer.

    Args:
        layer_name: Layer to control.
        locked: True to lock, False to unlock.
    """
    code = f'rs.LayerLocked("{layer_name}", {locked})\nprint("lock set")'
    resp = await conn.send_request(
        _exec_code(code, f"{'Lock' if locked else 'Unlock'} layer '{layer_name}'")
    )
    return resp.model_dump()


async def get_all_layers(
    conn: "RhinoConnection | MockRhinoConnection",
) -> dict[str, Any]:
    """Get a list of all layers in the document with their properties.

    Returns dict with layers list, each entry having name, color, visible, locked.
    """
    code = (
        "import json\n"
        "layers = rs.LayerNames()\n"
        "result = []\n"
        "if layers:\n"
        "    for lname in layers:\n"
        "        result.append({\n"
        "            'name': lname,\n"
        "            'visible': rs.LayerVisible(lname),\n"
        "            'locked': rs.LayerLocked(lname),\n"
        "            'color': list(rs.LayerColor(lname)),\n"
        "        })\n"
        "print(json.dumps(result))\n"
    )
    resp = await conn.send_request(_exec_code(code, "Get all layers"))
    return resp.model_dump()


async def delete_layer(
    conn: "RhinoConnection | MockRhinoConnection",
    layer_name: str,
    delete_objects: bool = False,
) -> dict[str, Any]:
    """Delete a layer.

    Args:
        layer_name: Layer to delete.
        delete_objects: If True, also delete objects on the layer.
    """
    if delete_objects:
        code = (
            f'objs = rs.ObjectsByLayer("{layer_name}")\n'
            f"if objs: rs.DeleteObjects(objs)\n"
            f'rs.DeleteLayer("{layer_name}")\n'
            f"print('layer deleted')\n"
        )
    else:
        code = f'rs.DeleteLayer("{layer_name}")\nprint("layer deleted")\n'
    resp = await conn.send_request(_exec_code(code, f"Delete layer '{layer_name}'"))
    return resp.model_dump()


async def set_current_layer(
    conn: "RhinoConnection | MockRhinoConnection",
    layer_name: str,
) -> dict[str, Any]:
    """Set the active layer for new objects.

    Args:
        layer_name: Layer to make current.
    """
    code = f'rs.CurrentLayer("{layer_name}")\nprint("current layer set")'
    resp = await conn.send_request(
        _exec_code(code, f"Set current layer to '{layer_name}'")
    )
    return resp.model_dump()
