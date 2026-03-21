# RhinoMCP Plugin — Command executor module
# IronPython 2.7 compatible: no f-strings, no type hints, no dataclasses

import sys
import time
import traceback

try:
    import rhinoscriptsyntax as rs
    import Rhino
    RHINO_AVAILABLE = True
except ImportError:
    RHINO_AVAILABLE = False


def execute_code(code, timeout=30):
    """
    Execute rhinoscriptsyntax Python code inside Rhino.

    The execution namespace pre-imports:
        import rhinoscriptsyntax as rs
        import Rhino
        import Rhino.Geometry as rg

    Args:
        code (str): Python code to execute.
        timeout (int): Timeout in seconds (best-effort for long loops).

    Returns:
        dict: {
            status: 'success' | 'error',
            output: captured stdout,
            error_message: str or None,
            error_type: str or None,
            traceback: str or None,
            execution_time_ms: int,
        }
    """
    if not RHINO_AVAILABLE:
        return {
            "status": "error",
            "output": "",
            "error_message": "Rhino is not available in this environment",
            "error_type": "ImportError",
            "traceback": None,
            "execution_time_ms": 0,
        }

    # Capture stdout
    old_stdout = sys.stdout
    from io import StringIO
    output_buffer = StringIO()
    sys.stdout = output_buffer

    start_time = time.time()
    error_info = None

    try:
        exec_globals = {
            "__builtins__": __builtins__,
            "rs": rs,
            "Rhino": Rhino,
        }
        try:
            import Rhino.Geometry as rg
            exec_globals["rg"] = rg
        except Exception:
            pass

        # Use Rhino UI thread for safety
        def _run():
            exec(code, exec_globals)

        if hasattr(Rhino.RhinoApp, "InvokeOnUiThread"):
            Rhino.RhinoApp.InvokeOnUiThread(_run)
        else:
            _run()

        status = "success"
    except Exception as exc:
        error_info = {
            "error_message": str(exc),
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
        }
        status = "error"
    finally:
        sys.stdout = old_stdout

    elapsed_ms = int((time.time() - start_time) * 1000)
    output = output_buffer.getvalue()

    result = {
        "status": status,
        "output": output,
        "execution_time_ms": elapsed_ms,
        "error_message": None,
        "error_type": None,
        "traceback": None,
    }

    if error_info:
        result.update(error_info)
        # Provide structured suggestions for common errors
        result["suggestions"] = _suggest_fixes(error_info["error_type"], error_info["error_message"])

    return result


def _suggest_fixes(error_type, error_message):
    """Map common error types to actionable suggestions."""
    suggestions = []
    msg = (error_message or "").lower()

    if "not closed" in msg or "not a solid" in msg:
        suggestions.append("Use rs.IsBrep() to check the object type before boolean operations")
        suggestions.append("Use Cap command to close open surfaces")

    if "do not intersect" in msg or "no intersection" in msg:
        suggestions.append("Use rs.BoundingBox() to verify objects overlap in space")
        suggestions.append("Move one object so it intersects the other before the operation")

    if "nameerror" in error_type.lower():
        if "rs" in msg:
            suggestions.append("Add 'import rhinoscriptsyntax as rs' at the top of the code")
        if "rg" in msg:
            suggestions.append("Add 'import Rhino.Geometry as rg' at the top")

    if "attributeerror" in error_type.lower():
        suggestions.append("Check the rhinoscriptsyntax documentation for the correct function name")
        suggestions.append("The function may have a different name in Rhino 8 vs Rhino 7")

    if "typeerror" in error_type.lower():
        suggestions.append("Check that all function arguments have the correct type")
        suggestions.append("rhinoscriptsyntax expects tuples or lists for point coordinates")

    if not suggestions:
        suggestions.append("Check the Rhino command history for more details")
        suggestions.append("Use execute_rhinoscript with simpler test code to isolate the issue")

    return suggestions
