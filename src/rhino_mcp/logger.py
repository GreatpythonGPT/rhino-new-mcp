"""Structured JSON logging for RhinoMCP.

All log records are emitted as JSON for easy parsing by AI agents.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }

        # Include structured extras if present
        for key in ("action", "input", "output", "duration_ms", "scene_state_after"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """Get a structured JSON logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger


class TimedOperation:
    """Context manager that logs structured timing info."""

    def __init__(
        self,
        logger: logging.Logger,
        action: str,
        input_data: dict[str, Any] | None = None,
        level: int = logging.INFO,
    ):
        self.logger = logger
        self.action = action
        self.input_data = input_data or {}
        self.level = level
        self._start: float = 0.0

    def __enter__(self) -> "TimedOperation":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration_ms = int((time.monotonic() - self._start) * 1000)
        extra: dict[str, Any] = {
            "action": self.action,
            "input": self.input_data,
            "duration_ms": duration_ms,
        }
        if exc_type is not None:
            extra["output"] = {"status": "error", "error": str(exc_val)}
            self.logger.error(
                f"{self.action} failed after {duration_ms}ms",
                extra=extra,
                exc_info=(exc_type, exc_val, exc_tb),
            )
        else:
            self.logger.log(
                self.level,
                f"{self.action} completed in {duration_ms}ms",
                extra=extra,
            )

    def set_output(self, output: dict[str, Any]) -> None:
        """Set the output data (call before __exit__)."""
        self._output = output
