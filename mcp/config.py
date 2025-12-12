"""
Configuration constants and enums for Agent² MCP Server.

This module centralizes all configuration to make the codebase
easier to maintain and customize.

Environment Variables:
    CURSOR_API_KEY: API key for Cursor CLI authentication
    CURSOR_MODEL: Model to use for all agents (default: composer-1)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


# ==============================================================================
# PATH CONFIGURATION
# ==============================================================================

# Workspace directory (where agent-squared lives)
WORKSPACE_DIR = Path(__file__).parent.resolve()

# Common cursor-agent installation paths
CURSOR_AGENT_PATHS = [
    os.path.expanduser("~/.local/bin/cursor-agent"),
    os.path.expanduser("~/.cursor/bin/cursor-agent"),
    "/usr/local/bin/cursor-agent",
]


# ==============================================================================
# MODEL CONFIGURATION
# ==============================================================================

# Default model for all agents - can be overridden via CURSOR_MODEL env var
# Common options: composer-1, claude-sonnet-4, gpt-4o, etc.
DEFAULT_MODEL = "composer-1"


def get_model() -> str:
    """
    Get the configured model for agent execution.
    
    Uses CURSOR_MODEL environment variable if set, otherwise falls back
    to DEFAULT_MODEL.
    
    Returns:
        Model identifier string.
    """
    return os.environ.get("CURSOR_MODEL", DEFAULT_MODEL)


# ==============================================================================
# MCP SERVER CONFIGURATION
# ==============================================================================

@dataclass(frozen=True)
class MCPConfig:
    """Configuration constants for the MCP server."""

    timeout_seconds: int = 90  # Max time per agent call
    max_output_length: int = 2000  # Truncate agent output after this
    max_composer_output_length: int = 1500
    max_modified_files_shown: int = 20
    git_timeout_seconds: int = 10


# Singleton config instance
CONFIG = MCPConfig()

# Default timeout for agent execution (in seconds)
DEFAULT_TIMEOUT = 600


# ==============================================================================
# TOOL NAMES
# ==============================================================================

class ToolName(str, Enum):
    """Enumeration of available tool names for type safety."""

    # Main entry point
    AGENT_SQUARED = "agent_squared"
    
    # Pipeline steps
    SPLIT_TASK = "split_task"
    PERFECT_PROMPT = "perfect_prompt"
    RUN_SPECIALIST = "run_specialist"
    COMPOSE_AGENTS = "compose_agents"
    
    # All-in-one
    AGENT_CHAIN = "agent_chain"
    
    # Utilities
    LIST_AGENTS = "list_agents"
    GET_CLARIFYING_QUESTIONS = "get_clarifying_questions"
    CHECK_TASK_READINESS = "check_task_readiness"
    TEST_CURSOR_CLI = "test_cursor_cli"
