"""
LEAN-Ops MCP Server
===================
MCP server for QuantConnect LEAN algorithm operations.
"""

__version__ = "1.0.0"

from .server import main

__all__ = ["main", "__version__"]
