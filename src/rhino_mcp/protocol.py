"""Communication protocol definitions for RhinoMCP.

JSON-based protocol over TCP socket between MCP Server and Rhino plugin.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    EXECUTE_COMMAND = "execute_command"
    QUERY_STATE = "query_state"
    CAPTURE_VIEWPORT = "capture_viewport"
    SELECT_OBJECTS = "select_objects"
    HEALTH_CHECK = "health_check"


class RequestStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    MOCK = "mock"


class ExecutePayload(BaseModel):
    code: str = Field(..., description="rhinoscriptsyntax Python code to execute")
    timeout: int = Field(30, description="Execution timeout in seconds")
    description: str = Field("", description="Human-readable description for logging")


class QueryStatePayload(BaseModel):
    include_geometry: bool = Field(False, description="Include detailed geometry info")
    layer_filter: str | None = Field(None, description="Filter objects by layer name")


class CaptureViewportPayload(BaseModel):
    view_name: str = Field("Perspective", description="Viewport name to capture")
    width: int = Field(1280, description="Image width in pixels")
    height: int = Field(720, description="Image height in pixels")
    annotate_objects: list[str] = Field(
        default_factory=list,
        description="List of object GUIDs to annotate in the capture",
    )


class SelectObjectsPayload(BaseModel):
    filter_type: str | None = Field(
        None, description="Object type filter: curve, surface, brep, mesh, etc."
    )
    filter_layer: str | None = Field(None, description="Layer name filter")
    filter_near_point: tuple[float, float, float] | None = Field(
        None, description="Select objects near this point"
    )
    filter_near_radius: float = Field(
        10.0, description="Radius for near-point selection"
    )
    semantic_description: str = Field(
        "", description="Natural language description of target objects"
    )


class RhinoRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)


class SceneObject(BaseModel):
    id: str
    type: str
    layer: str
    name: str = ""
    visible: bool = True


class SceneSummary(BaseModel):
    total_objects: int
    last_created: SceneObject | None = None
    layers: list[str] = Field(default_factory=list)
    document_name: str = ""
    unit_system: str = "Millimeters"


class ErrorDetail(BaseModel):
    type: str
    message: str
    code: str
    context: dict[str, Any] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)


class CommandResult(BaseModel):
    created_objects: list[str] = Field(default_factory=list)
    modified_objects: list[str] = Field(default_factory=list)
    deleted_objects: list[str] = Field(default_factory=list)
    execution_time_ms: int = 0
    scene_summary: SceneSummary | None = None
    output: str = ""


class RhinoResponse(BaseModel):
    id: str
    status: RequestStatus
    result: dict[str, Any] | None = None
    error: ErrorDetail | None = None
    mock: bool = False

    @classmethod
    def make_success(
        cls, request_id: str, result: dict[str, Any], mock: bool = False
    ) -> "RhinoResponse":
        return cls(
            id=request_id,
            status=RequestStatus.MOCK if mock else RequestStatus.SUCCESS,
            result=result,
            mock=mock,
        )

    @classmethod
    def make_error(
        cls,
        request_id: str,
        error_type: str,
        message: str,
        code: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> "RhinoResponse":
        return cls(
            id=request_id,
            status=RequestStatus.ERROR,
            error=ErrorDetail(
                type=error_type,
                message=message,
                code=code,
                context=context or {},
                suggestions=suggestions or [],
            ),
        )

    @classmethod
    def make_timeout(cls, request_id: str, timeout_seconds: int) -> "RhinoResponse":
        return cls(
            id=request_id,
            status=RequestStatus.TIMEOUT,
            error=ErrorDetail(
                type="CommandTimeout",
                message=f"Command timed out after {timeout_seconds}s",
                code="TIMEOUT",
                suggestions=[
                    "Increase the timeout parameter",
                    "Check if Rhino is responsive",
                    "Break complex operations into smaller steps",
                ],
            ),
        )


# Common error codes
class ErrorCode:
    BOOL_NO_INTERSECTION = "BOOL_NO_INTERSECTION"
    BOOL_NOT_CLOSED = "BOOL_NOT_CLOSED"
    OBJECT_NOT_FOUND = "OBJECT_NOT_FOUND"
    INVALID_GEOMETRY = "INVALID_GEOMETRY"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    CONNECTION_LOST = "CONNECTION_LOST"
    TIMEOUT = "TIMEOUT"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    LAYER_NOT_FOUND = "LAYER_NOT_FOUND"
    VIEWPORT_NOT_FOUND = "VIEWPORT_NOT_FOUND"
    SELECTION_AMBIGUOUS = "SELECTION_AMBIGUOUS"
    SELECTION_EMPTY = "SELECTION_EMPTY"
