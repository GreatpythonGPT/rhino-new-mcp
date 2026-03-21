# RhinoMCP — AI-Driven Rhino 3D Modeling via MCP

Control Rhino 3D with AI agents using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

## Architecture

```
User (natural language)
    │
    ▼
AI Agent (Claude, etc.)
    │  MCP protocol
    ▼
RhinoMCP Server (this repo)
    │  TCP socket (localhost:9876)
    ▼
Rhino Plugin (socket_server.py)
    │
    ▼
rhinoscriptsyntax / RhinoCommon → Rhino 8
```

## Quick Start

### 1. Install the MCP Server

```bash
pip install -e ".[dev]"
```

### 2. Install the Rhino Plugin

```bash
python scripts/install_rhino_plugin.py
```

Follow the printed instructions to load the plugin into Rhino.

### 3. Start in Mock Mode (no Rhino required)

```bash
rhino-mcp --mock
```

### 4. Start with real Rhino

First start Rhino and load the plugin (see Step 2), then:

```bash
rhino-mcp
```

## Available MCP Tools

### Geometry Creation
| Tool | Description |
|------|-------------|
| `create_sphere` | Create a sphere |
| `create_box` | Create a rectangular solid |
| `create_cylinder` | Create a cylinder |
| `create_cone` | Create a cone |
| `create_torus` | Create a torus (donut) |
| `create_line` | Create a line curve |
| `create_circle` | Create a circle |
| `create_polyline` | Create a polyline |
| `extrude_curve` | Extrude a profile curve |

### Transforms
| Tool | Description |
|------|-------------|
| `move_object` | Move or copy an object |
| `rotate_object` | Rotate around an axis |
| `scale_object` | Scale uniformly or non-uniformly |
| `mirror_object` | Mirror across a plane |
| `array_linear` | Linear array |
| `array_polar` | Polar (rotational) array |

### Boolean Operations
| Tool | Description |
|------|-------------|
| `boolean_difference` | Subtract solids (B-diff) |
| `boolean_union` | Join solids |
| `boolean_intersection` | Keep overlap only |
| `fillet_edges` | Round edges |

### Surface Modeling
| Tool | Description |
|------|-------------|
| `loft` | Loft through cross-sections |
| `sweep1` | Sweep along one rail |
| `sweep2` | Sweep along two rails |
| `revolve` | Revolve a profile |
| `pipe` | Create pipe along curve |
| `offset_surface` | Offset surface/solid |

### Selection
| Tool | Description |
|------|-------------|
| `select_by_layer` | Get objects on a layer |
| `select_by_type` | Get objects by type |
| `select_closest_to_point` | Find nearest objects |
| `get_all_objects` | List all objects |

### Viewport
| Tool | Description |
|------|-------------|
| `capture_viewport` | Screenshot a viewport |
| `set_standard_view` | Switch to standard view |
| `zoom_to_object` | Zoom to an object |

### Scene & Layers
| Tool | Description |
|------|-------------|
| `get_scene_state` | Full scene snapshot |
| `get_object_info` | Object details |
| `delete_objects` | Delete objects |
| `set_object_name` | Name an object |
| `undo` | Undo operations |
| `create_layer` | Create a layer |
| `set_object_layer` | Move to layer |
| `get_all_layers` | List all layers |

### Fallback
| Tool | Description |
|------|-------------|
| `execute_rhinoscript` | Run arbitrary rhinoscriptsyntax code |
| `health_check` | Check server/Rhino status |

## Development

### Run Tests (Mock Mode — no Rhino needed)

```bash
pytest tests/ -v
```

### Health Check

```bash
python scripts/health_check.py
```

### Project Structure

```
rhino-mcp/
├── src/
│   ├── rhino_mcp/           # MCP Server
│   │   ├── server.py        # Main entry point
│   │   ├── connection.py    # TCP connection management
│   │   ├── protocol.py      # JSON protocol definitions
│   │   ├── mock.py          # Mock mode (no Rhino needed)
│   │   ├── logger.py        # Structured JSON logging
│   │   └── tools/           # MCP tool implementations
│   │       ├── geometry.py  # Primitives
│   │       ├── transform.py # Move/rotate/scale
│   │       ├── boolean.py   # Boolean ops
│   │       ├── surface.py   # Loft/sweep/revolve
│   │       ├── selection.py # Object selection
│   │       ├── viewport.py  # Screenshots/views
│   │       ├── scene.py     # Scene queries
│   │       ├── layers.py    # Layer management
│   │       └── execute.py   # Fallback executor
│   └── rhino_plugin/        # Rhino-side plugin
│       ├── socket_server.py # TCP server in Rhino
│       ├── executor.py      # Code executor
│       ├── state.py         # Scene state
│       └── viewport.py      # Viewport control
├── tests/
├── scripts/
│   ├── health_check.py
│   └── install_rhino_plugin.py
└── pyproject.toml
```

## Communication Protocol

Request (MCP Server → Rhino):
```json
{
  "id": "uuid",
  "type": "execute_command",
  "payload": {
    "code": "import rhinoscriptsyntax as rs\nrs.AddSphere((0,0,0), 5)",
    "timeout": 30
  }
}
```

Response (Rhino → MCP Server):
```json
{
  "id": "uuid",
  "status": "success",
  "result": {
    "created_objects": ["guid-xxx"],
    "execution_time_ms": 120,
    "scene_summary": {
      "total_objects": 15,
      "document_name": "Untitled"
    }
  },
  "error": null
}
```

## Claude Desktop Configuration

```json
{
  "mcpServers": {
    "rhino": {
      "command": "rhino-mcp",
      "args": [],
      "env": {
        "RHINO_HOST": "localhost",
        "RHINO_PORT": "9876"
      }
    }
  }
}
```

## Requirements

- Python 3.10+
- Rhino 8 (for real execution; not needed for mock/testing)
- `mcp`, `pydantic`, `anyio`
