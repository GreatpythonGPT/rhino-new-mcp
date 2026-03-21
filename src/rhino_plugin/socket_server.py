# RhinoMCP Plugin — TCP Socket Server
# Runs INSIDE Rhino's Python environment (IronPython 2.7 / CPython 3).
# IronPython 2.7 compatible: no f-strings, no type hints, no dataclasses.
#
# USAGE (from Rhino command line):
#   _RunPythonScript "C:/path/to/rhino_plugin/socket_server.py"
#
# Or from Rhino Python editor:
#   import socket_server; socket_server.start()

from __future__ import print_function

import json
import socket
import struct
import sys
import threading
import time
import traceback

# Plugin modules
try:
    from executor import execute_code
    from state import get_scene_state
    from viewport import capture_viewport
except ImportError:
    # When run directly as a script, adjust path
    import os
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)
    from executor import execute_code
    from state import get_scene_state
    from viewport import capture_viewport

HOST = "localhost"
PORT = 9876
HEADER_SIZE = 4  # 4-byte big-endian uint32 length prefix
MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10 MB

_server_running = False
_server_thread = None


def _recv_message(conn):
    """Receive a length-prefixed message from the socket."""
    header = _recv_exactly(conn, HEADER_SIZE)
    if header is None:
        return None
    msg_len = struct.unpack(">I", header)[0]
    if msg_len > MAX_MESSAGE_SIZE:
        raise ValueError("Message too large: {0} bytes".format(msg_len))
    body = _recv_exactly(conn, msg_len)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))


def _recv_exactly(conn, n):
    """Read exactly n bytes from socket."""
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def _send_message(conn, response_dict):
    """Send a length-prefixed JSON message."""
    body = json.dumps(response_dict, ensure_ascii=False).encode("utf-8")
    header = struct.pack(">I", len(body))
    conn.sendall(header + body)


def _handle_request(request):
    """
    Route an incoming request to the appropriate handler.

    Args:
        request (dict): Parsed JSON request with 'id', 'type', 'payload'.

    Returns:
        dict: Response to send back.
    """
    req_id = request.get("id", "unknown")
    req_type = request.get("type", "")
    payload = request.get("payload", {})

    try:
        if req_type == "execute_command":
            code = payload.get("code", "")
            timeout = payload.get("timeout", 30)
            exec_result = execute_code(code, timeout=timeout)

            if exec_result["status"] == "success":
                # Build scene summary after execution
                scene = get_scene_state(include_geometry=False)
                scene_summary = scene.get("scene_summary", {})
                return {
                    "id": req_id,
                    "status": "success",
                    "result": {
                        "created_objects": [],  # Populated from exec output if GUIDs printed
                        "modified_objects": [],
                        "deleted_objects": [],
                        "execution_time_ms": exec_result["execution_time_ms"],
                        "output": exec_result.get("output", ""),
                        "scene_summary": scene_summary,
                    },
                    "error": None,
                }
            else:
                return {
                    "id": req_id,
                    "status": "error",
                    "result": None,
                    "error": {
                        "type": exec_result.get("error_type", "ExecutionError"),
                        "message": exec_result.get("error_message", "Unknown error"),
                        "code": "EXECUTION_FAILED",
                        "context": {
                            "code_preview": code[:200],
                            "traceback": exec_result.get("traceback", ""),
                        },
                        "suggestions": exec_result.get("suggestions", []),
                    },
                }

        elif req_type == "query_state":
            include_geo = payload.get("include_geometry", False)
            layer_filter = payload.get("layer_filter")
            state = get_scene_state(include_geometry=include_geo, layer_filter=layer_filter)
            return {
                "id": req_id,
                "status": "success",
                "result": state,
                "error": None,
            }

        elif req_type == "capture_viewport":
            view_name = payload.get("view_name", "Perspective")
            width = payload.get("width", 1280)
            height = payload.get("height", 720)
            annotate = payload.get("annotate_objects", [])
            cap_result = capture_viewport(view_name, width, height, annotate)
            return {
                "id": req_id,
                "status": "success",
                "result": cap_result,
                "error": None,
            }

        elif req_type == "health_check":
            try:
                import Rhino
                rhino_version = str(Rhino.RhinoApp.Version)
                doc = Rhino.RhinoDoc.ActiveDoc
                doc_name = doc.Name or "Untitled"
                obj_count = doc.Objects.Count
                unit_system = str(doc.ModelUnitSystem)
            except Exception:
                rhino_version = "unknown"
                doc_name = "unknown"
                obj_count = 0
                unit_system = "unknown"

            return {
                "id": req_id,
                "status": "success",
                "result": {
                    "mcp_server": "running",
                    "rhino_connection": "connected",
                    "rhino_version": rhino_version,
                    "socket_port": PORT,
                    "mock_mode": False,
                    "scene_status": {
                        "document_name": doc_name,
                        "object_count": obj_count,
                        "unit_system": unit_system,
                    },
                },
                "error": None,
            }

        elif req_type == "select_objects":
            # Delegate to execute_code with a selection query
            filter_type = payload.get("filter_type")
            filter_layer = payload.get("filter_layer")

            if filter_layer:
                code = 'import rhinoscriptsyntax as rs\nprint([str(x) for x in (rs.ObjectsByLayer("{0}") or [])])'.format(filter_layer)
            elif filter_type:
                type_map = {
                    "curve": "rs.filter.curve",
                    "surface": "rs.filter.surface",
                    "brep": "rs.filter.polysurface",
                    "mesh": "rs.filter.mesh",
                    "point": "rs.filter.point",
                }
                rs_filter = type_map.get(filter_type.lower(), "rs.filter.object")
                code = 'import rhinoscriptsyntax as rs\nprint([str(x) for x in (rs.ObjectsByType({0}) or [])])'.format(rs_filter)
            else:
                code = 'import rhinoscriptsyntax as rs\nprint([str(x) for x in (rs.AllObjects() or [])])'

            exec_result = execute_code(code, timeout=15)
            return {
                "id": req_id,
                "status": "success",
                "result": {
                    "selected_objects": [],
                    "output": exec_result.get("output", ""),
                    "selection_method": "filter",
                },
                "error": None,
            }

        else:
            return {
                "id": req_id,
                "status": "error",
                "result": None,
                "error": {
                    "type": "UnknownRequestType",
                    "message": "Unknown request type: {0}".format(req_type),
                    "code": "UNKNOWN_TYPE",
                    "context": {},
                    "suggestions": ["Valid types: execute_command, query_state, capture_viewport, health_check, select_objects"],
                },
            }

    except Exception as exc:
        return {
            "id": req_id,
            "status": "error",
            "result": None,
            "error": {
                "type": "InternalError",
                "message": str(exc),
                "code": "INTERNAL_ERROR",
                "context": {"traceback": traceback.format_exc()},
                "suggestions": ["Check the Rhino plugin logs for more details"],
            },
        }


def _client_handler(conn, addr):
    """Handle a single client connection in a thread."""
    print("[RhinoMCP] Client connected: {0}".format(addr))
    try:
        while True:
            request = _recv_message(conn)
            if request is None:
                print("[RhinoMCP] Client disconnected: {0}".format(addr))
                break
            response = _handle_request(request)
            _send_message(conn, response)
    except Exception as exc:
        print("[RhinoMCP] Client error: {0}".format(exc))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _server_loop(server_sock):
    """Main server accept loop (runs in a thread)."""
    global _server_running
    print("[RhinoMCP] Socket server listening on {0}:{1}".format(HOST, PORT))
    while _server_running:
        try:
            server_sock.settimeout(1.0)
            conn, addr = server_sock.accept()
            t = threading.Thread(target=_client_handler, args=(conn, addr))
            t.daemon = True
            t.start()
        except socket.timeout:
            continue
        except Exception as exc:
            if _server_running:
                print("[RhinoMCP] Accept error: {0}".format(exc))
            break
    print("[RhinoMCP] Server stopped")


def start(host=HOST, port=PORT):
    """Start the RhinoMCP socket server."""
    global _server_running, _server_thread

    if _server_running:
        print("[RhinoMCP] Server is already running on port {0}".format(port))
        return

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(5)

    _server_running = True
    _server_thread = threading.Thread(target=_server_loop, args=(server_sock,))
    _server_thread.daemon = True
    _server_thread.start()

    print("[RhinoMCP] Server started on {0}:{1}".format(host, port))
    print("[RhinoMCP] The MCP Server can now connect to Rhino.")
    return server_sock


def stop():
    """Stop the RhinoMCP socket server."""
    global _server_running
    _server_running = False
    print("[RhinoMCP] Server stopping...")


# Auto-start when run as a script from Rhino
if __name__ == "__main__":
    start()
    print("[RhinoMCP] Type stop() to stop the server")
