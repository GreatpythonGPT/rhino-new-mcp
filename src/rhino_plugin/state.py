# RhinoMCP Plugin — Scene state query module
# IronPython 2.7 compatible: no f-strings, no type hints, no dataclasses

import json

try:
    import rhinoscriptsyntax as rs
    import Rhino
    import Rhino.Geometry as rg
    RHINO_AVAILABLE = True
except ImportError:
    RHINO_AVAILABLE = False


def get_scene_state(include_geometry=False, layer_filter=None):
    """
    Query and return current scene state as a dict.

    Args:
        include_geometry (bool): Include detailed geometry info.
        layer_filter (str): Filter objects by layer name.

    Returns:
        dict with objects, layers, document info.
    """
    if not RHINO_AVAILABLE:
        return _mock_state()

    doc = Rhino.RhinoDoc.ActiveDoc
    objects = []

    for rhino_obj in doc.Objects:
        if rhino_obj.IsDeleted:
            continue
        if layer_filter:
            layer_name = doc.Layers[rhino_obj.Attributes.LayerIndex].FullPath
            if layer_filter not in layer_name:
                continue

        obj_data = {
            "id": str(rhino_obj.Id),
            "type": _get_type_name(rhino_obj),
            "layer": doc.Layers[rhino_obj.Attributes.LayerIndex].FullPath,
            "name": rhino_obj.Attributes.Name or "",
            "visible": rhino_obj.IsVisible,
        }

        if include_geometry:
            bb = rhino_obj.Geometry.GetBoundingBox(True)
            if bb.IsValid:
                obj_data["bounding_box"] = {
                    "min": [bb.Min.X, bb.Min.Y, bb.Min.Z],
                    "max": [bb.Max.X, bb.Max.Y, bb.Max.Z],
                }
            try:
                mp = rg.AreaMassProperties.Compute(rhino_obj.Geometry)
                if mp:
                    obj_data["area"] = mp.Area
            except Exception:
                pass
            try:
                vp = rg.VolumeMassProperties.Compute(rhino_obj.Geometry)
                if vp:
                    obj_data["volume"] = vp.Volume
            except Exception:
                pass

        objects.append(obj_data)

    layers = [doc.Layers[i].FullPath for i in range(doc.Layers.Count)
              if not doc.Layers[i].IsDeleted]

    scene_summary = {
        "total_objects": len(objects),
        "last_created": objects[-1] if objects else None,
        "layers": layers,
        "document_name": doc.Name or "Untitled",
        "unit_system": str(doc.ModelUnitSystem),
    }

    return {
        "scene_summary": scene_summary,
        "objects": objects,
    }


def _get_type_name(rhino_obj):
    """Return a human-readable type name for a RhinoObject."""
    geo = rhino_obj.Geometry
    geo_type = type(geo).__name__

    type_map = {
        "Brep": "Brep",
        "Extrusion": "Extrusion",
        "Mesh": "Mesh",
        "NurbsSurface": "Surface",
        "NurbsCurve": "Curve",
        "PolylineCurve": "Polyline",
        "ArcCurve": "Arc",
        "LineCurve": "Line",
        "Point": "Point",
        "TextEntity": "Text",
        "Hatch": "Hatch",
    }
    return type_map.get(geo_type, geo_type)


def _mock_state():
    return {
        "scene_summary": {
            "total_objects": 0,
            "last_created": None,
            "layers": ["Default"],
            "document_name": "MockDocument.3dm",
            "unit_system": "Millimeters",
        },
        "objects": [],
    }
