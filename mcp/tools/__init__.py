"""
MCP Tool handlers for Agent² system.

This package provides tool handlers organized by functionality:
- pipeline: Main Agent² pipeline tools (split_task, perfect_prompt, run_specialist, compose_agents)
- utilities: Utility tools (agent_squared, list_agents)
- diagnostics: Diagnostic tools (test_cursor_mcp)
"""

from tools.registry import register_tool, get_handler, TOOL_HANDLERS
from tools.pipeline import (
    run_split_task,
    run_perfect_prompt,
    run_specialist,
    run_compose_agents,
)
from tools.utilities import (
    run_agent_squared,
    run_list_agents,
)
from tools.diagnostics import run_test_cursor_mcp

__all__ = [
    # Registry
    "register_tool",
    "get_handler",
    "TOOL_HANDLERS",
    # Pipeline
    "run_split_task",
    "run_perfect_prompt",
    "run_specialist",
    "run_compose_agents",
    # Utilities
    "run_agent_squared",
    "run_list_agents",
    # Diagnostics
    "run_test_cursor_mcp",
]
