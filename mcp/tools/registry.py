"""
Tool registry for Agent² MCP Server.

Provides the decorator-based registration pattern for tool handlers.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from config import ToolName

# Type alias for tool handlers
ToolHandler = Callable[[dict[str, Any]], Awaitable[list[Any]]]

# Tool handler registry - maps tool names to their async handler functions
TOOL_HANDLERS: dict[str, ToolHandler] = {}


def register_tool(name: str | ToolName) -> Callable[[ToolHandler], ToolHandler]:
    """
    Decorator to register a tool handler.

    Args:
        name: The tool name (string or ToolName enum).

    Example:
        @register_tool(ToolName.SPLIT_TASK)
        async def run_split_task(args: dict) -> list[TextContent]:
            ...
    """
    tool_name = name.value if isinstance(name, ToolName) else name

    def decorator(func: ToolHandler) -> ToolHandler:
        TOOL_HANDLERS[tool_name] = func
        return func

    return decorator


def get_handler(name: str) -> ToolHandler | None:
    """
    Get a tool handler by name.

    Args:
        name: The tool name.

    Returns:
        The handler function or None if not found.
    """
    return TOOL_HANDLERS.get(name)
