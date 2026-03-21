"""Tests for protocol.py — data model serialization and error helpers."""

import pytest
from rhino_mcp.protocol import (
    ErrorCode,
    MessageType,
    RhinoRequest,
    RhinoResponse,
    RequestStatus,
    SceneObject,
    SceneSummary,
    ErrorDetail,
)


def test_rhino_request_has_auto_id():
    req = RhinoRequest(type=MessageType.EXECUTE_COMMAND, payload={"code": "print(1)"})
    assert req.id, "Request should have an auto-generated ID"
    assert len(req.id) > 0


def test_rhino_request_ids_are_unique():
    req1 = RhinoRequest(type=MessageType.EXECUTE_COMMAND, payload={})
    req2 = RhinoRequest(type=MessageType.EXECUTE_COMMAND, payload={})
    assert req1.id != req2.id


def test_rhino_request_serialization():
    req = RhinoRequest(type=MessageType.QUERY_STATE, payload={"include_geometry": True})
    json_str = req.model_dump_json()
    assert "query_state" in json_str
    assert "include_geometry" in json_str


def test_response_success_factory():
    resp = RhinoResponse.make_success("test-id", {"created_objects": ["guid-1"]})
    assert resp.id == "test-id"
    assert resp.status == RequestStatus.SUCCESS
    assert resp.error is None
    assert resp.result["created_objects"] == ["guid-1"]


def test_response_success_mock_factory():
    resp = RhinoResponse.make_success("test-id", {}, mock=True)
    assert resp.status == RequestStatus.MOCK
    assert resp.mock is True


def test_response_error_factory():
    resp = RhinoResponse.make_error(
        "test-id",
        "BooleanOperationFailed",
        "Objects do not intersect",
        ErrorCode.BOOL_NO_INTERSECTION,
        context={"bounding_box_overlap": False},
        suggestions=["Move objects closer"],
    )
    assert resp.status == RequestStatus.ERROR
    assert resp.error is not None
    assert resp.error.code == ErrorCode.BOOL_NO_INTERSECTION
    assert len(resp.error.suggestions) > 0
    assert resp.result is None


def test_response_timeout_factory():
    resp = RhinoResponse.make_timeout("test-id", 30)
    assert resp.status == RequestStatus.TIMEOUT
    assert resp.error.code == "TIMEOUT"
    assert "30" in resp.error.message


def test_scene_summary_model():
    last_obj = SceneObject(id="guid-1", type="Brep", layer="Default")
    summary = SceneSummary(
        total_objects=5,
        last_created=last_obj,
        layers=["Default", "Layer01"],
        document_name="Test.3dm",
        unit_system="Millimeters",
    )
    data = summary.model_dump()
    assert data["total_objects"] == 5
    assert data["last_created"]["id"] == "guid-1"
    assert "Millimeters" in data["unit_system"]


def test_response_round_trip():
    """Response should survive JSON round-trip."""
    original = RhinoResponse.make_success("abc", {"foo": "bar"})
    json_str = original.model_dump_json()
    restored = RhinoResponse.model_validate_json(json_str)
    assert restored.id == original.id
    assert restored.status == original.status
    assert restored.result == original.result


def test_error_detail_has_suggestions():
    error = ErrorDetail(
        type="BooleanFailed",
        message="No intersection",
        code=ErrorCode.BOOL_NO_INTERSECTION,
        suggestions=["Tip 1", "Tip 2"],
    )
    assert len(error.suggestions) == 2


def test_all_message_types_exist():
    expected = {"execute_command", "query_state", "capture_viewport", "select_objects", "health_check"}
    actual = {m.value for m in MessageType}
    assert expected == actual
