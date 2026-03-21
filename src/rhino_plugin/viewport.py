# RhinoMCP Plugin — Viewport control module
# IronPython 2.7 compatible: no f-strings, no type hints, no dataclasses

import os
import time

try:
    import rhinoscriptsyntax as rs
    import Rhino
    import Rhino.Geometry as rg
    RHINO_AVAILABLE = True
except ImportError:
    RHINO_AVAILABLE = False


def capture_viewport(view_name="Perspective", width=1280, height=720, annotate_objects=None):
    """
    Capture a screenshot of the named viewport.

    Args:
        view_name (str): Viewport name.
        width (int): Image width.
        height (int): Image height.
        annotate_objects (list): GUIDs to annotate (future: add labels).

    Returns:
        dict: {image_path, view_name, width, height, annotations}
    """
    if not RHINO_AVAILABLE:
        return {
            "image_path": "/tmp/mock_capture.png",
            "view_name": view_name,
            "width": width,
            "height": height,
            "annotations": [],
            "mock": True,
        }

    # Generate unique filename
    timestamp = int(time.time())
    tmpdir = os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))
    filename = "rhino_capture_{0}.png".format(timestamp)
    image_path = os.path.join(tmpdir, filename)

    try:
        view = _get_view(view_name)
        if view is None:
            return {"status": "error", "error_message": "View '{0}' not found".format(view_name)}

        # Set viewport size and capture
        view.Size = Rhino.Geometry.Size(width, height) if hasattr(Rhino.Geometry, "Size") else None
        result = Rhino.RhinoApp.RunScript(
            '_ViewCaptureToFile "{0}" {1} {2} _Enter'.format(image_path, width, height),
            False
        )

        annotations = []
        if annotate_objects:
            for guid_str in annotate_objects:
                annotations.append({
                    "object_id": guid_str,
                    "label": guid_str[:8],  # Short label
                })

        return {
            "image_path": image_path,
            "view_name": view_name,
            "width": width,
            "height": height,
            "annotations": annotations,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_message": str(exc),
            "image_path": None,
        }


def _get_view(view_name):
    """Get a Rhino viewport by name."""
    doc = Rhino.RhinoDoc.ActiveDoc
    for view in doc.Views:
        if view.ActiveViewport.Name == view_name:
            return view
    return None


def get_viewport_info():
    """Return info about all open viewports."""
    if not RHINO_AVAILABLE:
        return {"viewports": [{"name": "Perspective", "type": "perspective"}]}

    doc = Rhino.RhinoDoc.ActiveDoc
    viewports = []
    for view in doc.Views:
        vp = view.ActiveViewport
        viewports.append({
            "name": vp.Name,
            "is_perspective": vp.IsPerspectiveProjection,
            "is_parallel": vp.IsParallelProjection,
        })
    return {"viewports": viewports}
