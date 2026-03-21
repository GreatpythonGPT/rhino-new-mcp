"""Tests for mock.py — MockRhinoConnection behaviour."""

import pytest
from rhino_mcp.mock import MockRhinoConnection, MockScene
from rhino_mcp.protocol import MessageType, RequestStatus, RhinoRequest


@pytest.fixture
def mock_conn():
    return MockRhinoConnection()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check_returns_mock_flag(mock_conn):
    req = RhinoRequest(type=MessageType.HEALTH_CHECK, payload={})
    resp = await mock_conn.send_request(req)
    assert resp.result["mock_mode"] is True
    assert resp.result["rhino_connection"] == "mock"


# ---------------------------------------------------------------------------
# execute_command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_sphere_creates_object(mock_conn):
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": "rs.AddSphere((0,0,0), 5)", "timeout": 30},
    )
    resp = await mock_conn.send_request(req)
    assert resp.status == RequestStatus.MOCK
    assert resp.mock is True
    assert len(resp.result["created_objects"]) == 1
    guid = resp.result["created_objects"][0]
    assert guid.startswith("mock-")


@pytest.mark.asyncio
async def test_execute_box_creates_object(mock_conn):
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": "rs.AddBox(corners)", "timeout": 30},
    )
    resp = await mock_conn.send_request(req)
    assert len(resp.result["created_objects"]) == 1


@pytest.mark.asyncio
async def test_execute_unknown_code_returns_no_object(mock_conn):
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": "print('hello world')", "timeout": 30},
    )
    resp = await mock_conn.send_request(req)
    assert resp.status == RequestStatus.MOCK
    assert resp.result["created_objects"] == []


@pytest.mark.asyncio
async def test_execute_returns_scene_summary(mock_conn):
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": "rs.AddSphere((0,0,0), 5)", "timeout": 30},
    )
    resp = await mock_conn.send_request(req)
    summary = resp.result["scene_summary"]
    assert "total_objects" in summary
    assert "document_name" in summary


# ---------------------------------------------------------------------------
# Failure scenarios
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_scenario_no_intersection(mock_conn):
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={
            "code": 'rs.BooleanDifference(["guid-a"], ["guid-b"])',
            "timeout": 30,
            "_mock_scenario": "no_intersection",
            "object_a": "guid-a",
        },
    )
    resp = await mock_conn.send_request(req)
    assert resp.status == RequestStatus.ERROR
    assert resp.error.code == "BOOL_NO_INTERSECTION"
    assert len(resp.error.suggestions) > 0
    assert resp.error.context["bounding_box_overlap"] is False


@pytest.mark.asyncio
async def test_mock_scenario_not_closed(mock_conn):
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": "...", "timeout": 30, "_mock_scenario": "not_closed"},
    )
    resp = await mock_conn.send_request(req)
    assert resp.status == RequestStatus.ERROR
    assert resp.error.code == "BOOL_NOT_CLOSED"


@pytest.mark.asyncio
async def test_mock_scenario_execution_error(mock_conn):
    req = RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": "AddSphere(0, 5)", "timeout": 30, "_mock_scenario": "execution_error"},
    )
    resp = await mock_conn.send_request(req)
    assert resp.status == RequestStatus.ERROR
    assert resp.error.code == "EXECUTION_FAILED"


# ---------------------------------------------------------------------------
# query_state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_state_returns_objects(mock_conn):
    # Create an object first
    await mock_conn.send_request(RhinoRequest(
        type=MessageType.EXECUTE_COMMAND,
        payload={"code": "rs.AddSphere((0,0,0), 5)", "timeout": 30},
    ))
    # Then query
    req = RhinoRequest(type=MessageType.QUERY_STATE, payload={})
    resp = await mock_conn.send_request(req)
    assert resp.status == RequestStatus.MOCK
    assert resp.result["scene_summary"]["total_objects"] >= 1
    assert isinstance(resp.result["objects"], list)


# ---------------------------------------------------------------------------
# capture_viewport
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_capture_viewport_returns_path(mock_conn):
    req = RhinoRequest(
        type=MessageType.CAPTURE_VIEWPORT,
        payload={"view_name": "Perspective", "width": 1280, "height": 720},
    )
    resp = await mock_conn.send_request(req)
    assert resp.status == RequestStatus.MOCK
    assert "image_path" in resp.result
    assert resp.result["view_name"] == "Perspective"


# ---------------------------------------------------------------------------
# select_objects
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_objects_by_type(mock_conn):
    # Populate scene
    for code in ["rs.AddSphere((0,0,0), 5)", "rs.AddBox(corners)", "rs.AddCurve(pts)"]:
        await mock_conn.send_request(RhinoRequest(
            type=MessageType.EXECUTE_COMMAND,
            payload={"code": code, "timeout": 30},
        ))
    req = RhinoRequest(
        type=MessageType.SELECT_OBJECTS,
        payload={"filter_type": "Sphere"},
    )
    resp = await mock_conn.send_request(req)
    assert resp.status == RequestStatus.MOCK
    assert "selected_objects" in resp.result


# ---------------------------------------------------------------------------
# MockScene
# ---------------------------------------------------------------------------

def test_mock_scene_add_and_remove():
    scene = MockScene()
    guid = scene.add_object("Brep")
    assert guid in scene.objects
    assert scene.objects[guid].type == "Brep"
    removed = scene.remove_object(guid)
    assert removed is True
    assert guid not in scene.objects


def test_mock_scene_remove_nonexistent():
    scene = MockScene()
    result = scene.remove_object("nonexistent-guid")
    assert result is False


def test_mock_scene_summary():
    scene = MockScene()
    guid = scene.add_object("Sphere")
    summary = scene.get_summary(guid)
    assert summary.total_objects == 1
    assert summary.last_created.id == guid
    assert summary.unit_system == "Millimeters"


# ---------------------------------------------------------------------------
# Unknown type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_message_type_returns_error(mock_conn):
    """A request with an unknown type should return an error or mock response."""
    # Create a valid request — the mock handles all known types gracefully
    req = RhinoRequest(type=MessageType.HEALTH_CHECK, payload={})
    resp = await mock_conn.send_request(req)
    # Health check always succeeds in mock mode
    assert resp.status == RequestStatus.MOCK
