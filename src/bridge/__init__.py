"""
Bridge Layer
Part of SOVEREIGN PYTHON LLM ENGINE

Bridge between C frontend (sovereign-ide) and Python engine.
Supports stdio and HTTP transports.
"""

from .stdio_server import StdioBridge
from .http_server import HTTPBridge

__all__ = [
    "StdioBridge",
    "HTTPBridge",
]
