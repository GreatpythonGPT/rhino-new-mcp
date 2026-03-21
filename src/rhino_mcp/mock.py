"""Mock Rhino connection for testing without a running Rhino instance.

Allows full MCP Server development and testing without Rhino.
Returns structurally correct mock data for all operations.
"""

from __future__ import annotations

import uuid
from typing import Any

from .logger import get_logger
from .protocol import (
    ErrorCode,
    MessageType,
    RhinoRequest,
    RhinoResponse,
    SceneObject,
    SceneSummary,
)

logger = get_logger("rhino_mcp.mock")


def _mock_guid() -> str:
    return f"mock-{uuid.uuid4().hex[:8]}"


class MockScene:
    """In-memory scene state for mock mode."""

    def __init__(self) -> None:
        self.objects: dict[str, SceneObject] = {}
        self.layers: list[str] = ["Default"]
        self.document_name = "MockDocument.3dm"
        self.unit_system = "Millimeters"

    def add_object(self, obj_type: str, layer: str = "Default") -> str:
        guid = _mock_guid()
        self.objects[guid] = SceneObject(id=guid, type=obj_type, layer=layer)
        return guid

    def remove_object(self, guid: str) -> bool:
        if guid in self.objects:
            del self.objects[guid]
            return True
        return False

    def get_summary(self, last_guid: str | None = None) -> SceneSummary:
        last = None
        if last_guid and last_guid in self.objects:
            last = self.objects[last_guid]
        return SceneSummary(
            total_objects=len(self.objects),
            last_created=last,
            layers=self.layers,
            document_name=self.document_name,
            unit_system=self.unit_system,
        )


class MockRhinoConnection:
    """Simulates a Rhino TCP connection. Returns structurally correct fake data."""

    def __init__(self) -> None:
        self.scene = MockScene()
        self.connected = True
        logger.info("MockRhinoConnection initialized")

    async def send_request(self, request: RhinoRequest) -> RhinoResponse:
        """Dispatch mock request by type."""
        logger.debug(
            "Mock request",
            extra={"action": "mock_request", "input": {"type": request.type, "id": request.id}},
        )

        if request.type == MessageType.EXECUTE_COMMAND:
            return await self._handle_execute(request)
        elif request.type == MessageType.QUERY_STATE:
            return await self._handle_query_state(request)
        elif request.type == MessageType.CAPTURE_VIEWPORT:
            return await self._handle_capture_viewport(request)
        elif request.type == MessageType.SELECT_OBJECTS:
            return await self._handle_select_objects(request)
        elif request.type == MessageType.HEALTH_CHECK:
            return await self._handle_health_check(request)
        else:
            return RhinoResponse.make_error(
                request.id,
                "UnknownMessageType",
                f"Unknown message type: {request.type}",
                "UNKNOWN_TYPE",
            )

    async def _handle_execute(self, request: RhinoRequest) -> RhinoResponse:
        code: str = request.payload.get("code", "")
        mock_scenario: str = request.payload.get("_mock_scenario", "")

        # Simulate specific failure scenarios for testing
        if mock_scenario == "no_intersection":
            return RhinoResponse.make_error(
                request.id,
                "BooleanOperationFailed",
                "BooleanDifference failed: objects do not intersect",
                ErrorCode.BOOL_NO_INTERSECTION,
                context={
                    "object_a": request.payload.get("object_a", "unknown"),
                    "bounding_box_overlap": False,
                },
                suggestions=[
                    "检查两个物体的包围盒是否重叠",
                    "尝试移动物体使其相交",
                    "使用 rs.BoundingBox() 检查空间位置",
                ],
            )

        if mock_scenario == "not_closed":
            return RhinoResponse.make_error(
                request.id,
                "BooleanOperationFailed",
                "BooleanDifference failed: object is not a closed solid",
                ErrorCode.BOOL_NOT_CLOSED,
                context={"object_type": "Brep (open)"},
                suggestions=[
                    "使用 rs.IsBrep() 检查物体类型",
                    "确保所有参与布尔运算的物体都是封闭实体",
                    "使用 Cap 命令封闭开放实体",
                ],
            )

        if mock_scenario == "execution_error":
            return RhinoResponse.make_error(
                request.id,
                "ExecutionError",
                "Script execution failed: NameError: name 'rs' is not defined",
                ErrorCode.EXECUTION_FAILED,
                context={"code_preview": code[:100]},
                suggestions=["确保代码中 import rhinoscriptsyntax as rs"],
            )

        # Infer object type from code to populate mock scene
        obj_type = self._infer_object_type(code)
        created_guids = []
        if obj_type:
            guid = self.scene.add_object(obj_type)
            created_guids.append(guid)

        summary = self.scene.get_summary(created_guids[0] if created_guids else None)

        return RhinoResponse.make_success(
            request.id,
            {
                "created_objects": created_guids,
                "modified_objects": [],
                "deleted_objects": [],
                "execution_time_ms": 42,
                "scene_summary": summary.model_dump(),
                "output": f"[mock] executed: {code[:80]}{'...' if len(code) > 80 else ''}",
            },
            mock=True,
        )

    async def _handle_query_state(self, request: RhinoRequest) -> RhinoResponse:
        summary = self.scene.get_summary()
        objects_data = [obj.model_dump() for obj in self.scene.objects.values()]
        return RhinoResponse.make_success(
            request.id,
            {
                "scene_summary": summary.model_dump(),
                "objects": objects_data,
                "mock": True,
            },
            mock=True,
        )

    async def _handle_capture_viewport(self, request: RhinoRequest) -> RhinoResponse:
        view_name = request.payload.get("view_name", "Perspective")
        return RhinoResponse.make_success(
            request.id,
            {
                "view_name": view_name,
                "image_path": f"/tmp/mock_capture_{uuid.uuid4().hex[:8]}.png",
                "image_base64": None,
                "width": request.payload.get("width", 1280),
                "height": request.payload.get("height", 720),
                "annotations": [],
                "mock": True,
            },
            mock=True,
        )

    async def _handle_select_objects(self, request: RhinoRequest) -> RhinoResponse:
        filter_type = request.payload.get("filter_type")
        candidates = [
            obj
            for obj in self.scene.objects.values()
            if filter_type is None or obj.type.lower() == filter_type.lower()
        ]
        return RhinoResponse.make_success(
            request.id,
            {
                "selected_objects": [obj.id for obj in candidates[:5]],
                "total_candidates": len(candidates),
                "selection_method": "mock_filter",
                "mock": True,
            },
            mock=True,
        )

    async def _handle_health_check(self, request: RhinoRequest) -> RhinoResponse:
        summary = self.scene.get_summary()
        return RhinoResponse.make_success(
            request.id,
            {
                "mcp_server": "running",
                "rhino_connection": "mock",
                "rhino_version": "Mock 8.0",
                "socket_port": 9876,
                "mock_mode": True,
                "scene_status": {
                    "document_name": summary.document_name,
                    "object_count": summary.total_objects,
                    "unit_system": summary.unit_system,
                    "layers": summary.layers,
                },
            },
            mock=True,
        )

    def _infer_object_type(self, code: str) -> str | None:
        """Infer what kind of object a script creates for mock scene tracking."""
        code_lower = code.lower()
        type_map = {
            "addsphere": "Sphere",
            "addbox": "Box",
            "addcylinder": "Cylinder",
            "addcone": "Cone",
            "addtorus": "Torus",
            "addpolyline": "Polyline",
            "addcurve": "Curve",
            "addline": "Line",
            "addcircle": "Circle",
            "addarc": "Arc",
            "addellipse": "Ellipse",
            "addrectangle": "Rectangle",
            "addplanarsrf": "Surface",
            "addextrusion": "Extrusion",
            "extrudecurve": "Extrusion",
            "extrudecrvtapered": "Extrusion",
            "loft": "Brep",
            "sweep1": "Brep",
            "sweep2": "Brep",
            "revolve": "Brep",
            "booleandifference": "Brep",
            "booleanunion": "Brep",
            "booleanintersection": "Brep",
            "addmesh": "Mesh",
            "addpipe": "Pipe",
            "addtext": "TextObject",
        }
        for key, obj_type in type_map.items():
            if key in code_lower:
                return obj_type
        return None

    async def close(self) -> None:
        self.connected = False
        logger.info("MockRhinoConnection closed")
