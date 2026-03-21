"""Tests for MCP tool functions using mock connection."""

import pytest
from rhino_mcp.mock import MockRhinoConnection
from rhino_mcp.protocol import RequestStatus
from rhino_mcp.tools import (
    boolean,
    geometry,
    layers,
    scene,
    selection,
    surface,
    transform,
    viewport,
)


@pytest.fixture
def conn():
    return MockRhinoConnection()


# ---------------------------------------------------------------------------
# Geometry tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_sphere(conn):
    result = await geometry.create_sphere(conn, (0, 0, 0), 10.0)
    assert result["status"] in ("success (mock)", "mock")
    assert len(result["result"]["created_objects"]) == 1


@pytest.mark.asyncio
async def test_create_box(conn):
    result = await geometry.create_box(conn, (0, 0, 0), 10.0, 20.0, 5.0)
    assert result["status"] in ("success (mock)", "mock")
    assert len(result["result"]["created_objects"]) == 1


@pytest.mark.asyncio
async def test_create_cylinder(conn):
    result = await geometry.create_cylinder(conn, (0, 0, 0), 50.0, 15.0)
    assert result["result"]["created_objects"]


@pytest.mark.asyncio
async def test_create_cone(conn):
    result = await geometry.create_cone(conn, (0, 0, 0), 30.0, 10.0)
    assert result["result"]["created_objects"]


@pytest.mark.asyncio
async def test_create_torus(conn):
    result = await geometry.create_torus(conn, (0, 0, 0), 20.0, 5.0)
    assert result["result"]["created_objects"]


@pytest.mark.asyncio
async def test_create_line(conn):
    result = await geometry.create_line(conn, (0, 0, 0), (10, 10, 0))
    assert result["result"]["created_objects"]


@pytest.mark.asyncio
async def test_create_circle(conn):
    result = await geometry.create_circle(conn, (0, 0, 0), 5.0)
    assert result["result"]["created_objects"]


@pytest.mark.asyncio
async def test_create_polyline(conn):
    points = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
    result = await geometry.create_polyline(conn, points)
    assert result["status"] in ("success (mock)", "mock")
    assert result["result"]["created_objects"]


@pytest.mark.asyncio
async def test_create_sphere_with_layer(conn):
    result = await geometry.create_sphere(conn, (5, 5, 5), 3.0, layer="TestLayer")
    assert result["result"]["created_objects"]


@pytest.mark.asyncio
async def test_extrude_curve(conn):
    result = await geometry.extrude_curve(conn, "mock-curve-guid", (0, 0, 50), cap=True)
    assert result["result"]["created_objects"]


# ---------------------------------------------------------------------------
# Transform tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_move_object(conn):
    result = await transform.move_object(conn, "mock-guid-1", (10, 0, 0))
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_copy_object(conn):
    result = await transform.move_object(conn, "mock-guid-1", (10, 0, 0), copy=True)
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_rotate_object(conn):
    result = await transform.rotate_object(conn, "mock-guid-1", 45.0)
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_scale_uniform(conn):
    result = await transform.scale_object(conn, "mock-guid-1", 2.0)
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_scale_nonuniform(conn):
    result = await transform.scale_object(conn, "mock-guid-1", (1.0, 2.0, 3.0))
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_mirror_object(conn):
    result = await transform.mirror_object(conn, "mock-guid-1", (0, 0, 0), (0, 10, 0))
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_array_linear(conn):
    result = await transform.array_linear(conn, "mock-guid-1", 4, (20, 0, 0))
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_array_polar(conn):
    result = await transform.array_polar(conn, "mock-guid-1", 6, (0, 0, 0))
    assert result["status"] in ("success (mock)", "mock")


# ---------------------------------------------------------------------------
# Boolean tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_boolean_difference_success(conn):
    result = await boolean.boolean_difference(conn, "mock-a", ["mock-b", "mock-c"])
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_boolean_difference_no_intersection(conn):
    result = await boolean.boolean_difference(
        conn, "mock-a", ["mock-b"], _mock_scenario="no_intersection"
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "BOOL_NO_INTERSECTION"
    assert len(result["error"]["suggestions"]) > 0


@pytest.mark.asyncio
async def test_boolean_difference_not_closed(conn):
    result = await boolean.boolean_difference(
        conn, "mock-a", ["mock-b"], _mock_scenario="not_closed"
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "BOOL_NOT_CLOSED"


@pytest.mark.asyncio
async def test_boolean_union(conn):
    result = await boolean.boolean_union(conn, ["mock-a", "mock-b", "mock-c"])
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_boolean_intersection(conn):
    result = await boolean.boolean_intersection(conn, ["mock-a", "mock-b"])
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_fillet_edges(conn):
    result = await boolean.fillet_edges(conn, "mock-solid", [0, 1, 2], 3.0)
    assert result["status"] in ("success (mock)", "mock")


# ---------------------------------------------------------------------------
# Surface tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loft(conn):
    result = await surface.loft(conn, ["mock-curve-1", "mock-curve-2", "mock-curve-3"])
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_sweep1(conn):
    result = await surface.sweep1(conn, "mock-rail", ["mock-profile"])
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_sweep2(conn):
    result = await surface.sweep2(conn, "mock-rail1", "mock-rail2", ["mock-profile"])
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_revolve(conn):
    result = await surface.revolve(conn, "mock-profile", (0, 0, 0), (0, 0, 100))
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_pipe(conn):
    result = await surface.pipe(conn, "mock-rail", 5.0)
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_offset_surface(conn):
    result = await surface.offset_surface(conn, "mock-surface", 2.0)
    assert result["status"] in ("success (mock)", "mock")


# ---------------------------------------------------------------------------
# Selection tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_by_layer(conn):
    result = await selection.select_by_layer(conn, "Default")
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_select_by_type(conn):
    result = await selection.select_by_type(conn, "brep")
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_select_closest_to_point(conn):
    result = await selection.select_closest_to_point(conn, (0, 0, 0), count=3)
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_get_all_objects(conn):
    result = await selection.get_all_objects(conn)
    assert result["status"] in ("success (mock)", "mock")


# ---------------------------------------------------------------------------
# Viewport tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_capture_viewport(conn):
    result = await viewport.capture_viewport(conn, "Perspective", 1920, 1080)
    assert result["status"] in ("success (mock)", "mock")
    assert "image_path" in result["result"]


@pytest.mark.asyncio
async def test_set_standard_view(conn):
    result = await viewport.set_standard_view(conn, "Top")
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_zoom_to_object(conn):
    result = await viewport.zoom_to_object(conn, "mock-guid-1")
    assert result["status"] in ("success (mock)", "mock")


# ---------------------------------------------------------------------------
# Scene tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_scene_state(conn):
    result = await scene.get_scene_state(conn)
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_delete_objects(conn):
    result = await scene.delete_objects(conn, ["mock-a", "mock-b"])
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_set_object_name(conn):
    result = await scene.set_object_name(conn, "mock-guid", "MyBox")
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_undo(conn):
    result = await scene.undo(conn, steps=2)
    assert result["status"] in ("success (mock)", "mock")


# ---------------------------------------------------------------------------
# Layer tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_layer(conn):
    result = await layers.create_layer(conn, "Structure", (255, 0, 0))
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_set_object_layer(conn):
    result = await layers.set_object_layer(conn, "mock-guid", "Structure")
    assert result["status"] in ("success (mock)", "mock")


@pytest.mark.asyncio
async def test_get_all_layers(conn):
    result = await layers.get_all_layers(conn)
    assert result["status"] in ("success (mock)", "mock")
