"""
MCP Tool handlers for Agent² system.

This package provides tool handlers organized by functionality:
- pipeline: Main Agent² pipeline tools (split_task, perfect_prompt, run_specialist, compose_agents)
- utilities: Utility tools (list_agents, get_clarifying_questions, check_task_readiness)
- diagnostics: Diagnostic tools (test_cursor_cli)
"""

from tools.registry import register_tool, get_handler, TOOL_HANDLERS
from tools.pipeline import (
    run_agent_chain,
    run_split_task,
    run_perfect_prompt,
    run_specialist,
    run_compose_agents,
)
from tools.utilities import (
    run_list_agents,
    run_get_clarifying_questions,
    run_check_task_readiness,
)
from tools.diagnostics import run_test_cursor_cli

__all__ = [
    # Registry
    "register_tool",
    "get_handler",
    "TOOL_HANDLERS",
    # Pipeline
    "run_agent_chain",
    "run_split_task",
    "run_perfect_prompt",
    "run_specialist",
    "run_compose_agents",
    # Utilities
    "run_list_agents",
    "run_get_clarifying_questions",
    "run_check_task_readiness",
    # Diagnostics
    "run_test_cursor_cli",
]
