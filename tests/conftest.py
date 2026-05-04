"""Pytest compatibility helpers for environments without pytest-asyncio."""

from __future__ import annotations

import asyncio
import inspect


def pytest_pyfunc_call(pyfuncitem):
    """Run ``async def`` tests via ``asyncio.run`` when no async plugin is installed."""
    test_func = pyfuncitem.obj
    if inspect.iscoroutinefunction(test_func):
        asyncio.run(test_func(**pyfuncitem.funcargs))
        return True
    return None
