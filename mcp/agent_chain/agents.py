"""
Agent definitions for Agent² system.

This module contains all agent configurations including:
- Core specialist agents (frontend, backend, cloud, full-stack)
- Additional specialist agents (code-reviewer, python-pro, etc.)
- Special agents (splitter, prompt-engineer, composer)
- Custom user agents (from ~/.agent-squared/agents/ or AGENT_SQUARED_AGENTS_DIR)

Model Configuration:
    All agents use the model specified by CURSOR_MODEL environment variable.
    Default is "composer-1" if not set.

Custom Agents:
    Users can add their own agents by placing .md files in:
    1. ~/.agent-squared/agents/  (default location)
    2. A custom directory via AGENT_SQUARED_AGENTS_DIR environment variable
    
    Agent files should be named like: my-custom-agent.md
    The agent will be available as: my-custom-agent
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from config import get_model

logger = logging.getLogger("agent-squared")


# ==============================================================================
# CUSTOM AGENTS CONFIGURATION
# ==============================================================================

# Default location for custom agents
DEFAULT_CUSTOM_AGENTS_DIR = Path.home() / ".agent-squared" / "agents"

# Environment variable to override custom agents directory
CUSTOM_AGENTS_ENV_VAR = "AGENT_SQUARED_AGENTS_DIR"


def get_custom_agents_dir() -> Path | None:
    """
    Get the directory for custom user agents.
    
    Checks:
    1. AGENT_SQUARED_AGENTS_DIR environment variable
    2. ~/.agent-squared/agents/ default location
    
    Returns:
        Path to custom agents directory, or None if it doesn't exist.
    """
    # Check environment variable first
    env_dir = os.environ.get(CUSTOM_AGENTS_ENV_VAR)
    if env_dir:
        custom_dir = Path(env_dir).expanduser()
        if custom_dir.exists() and custom_dir.is_dir():
            return custom_dir
        else:
            logger.warning(f"Custom agents directory not found: {custom_dir}")
    
    # Check default location
    if DEFAULT_CUSTOM_AGENTS_DIR.exists() and DEFAULT_CUSTOM_AGENTS_DIR.is_dir():
        return DEFAULT_CUSTOM_AGENTS_DIR
    
    return None


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _agent(name: str, file: str) -> dict[str, Any]:
    """Create an agent config with the current model setting."""
    return {
        "name": name,
        "file": file,
        "model": get_model(),
    }


def _composite_agent(name: str, agents: list[str]) -> dict[str, Any]:
    """Create a composite agent config (runs multiple sub-agents)."""
    return {
        "name": name,
        "agents": agents,
        "model": get_model(),
    }


# ==============================================================================
# CORE SPECIALIST AGENTS
# ==============================================================================

# Core specialist agents - paths relative to project root (parent of mcp/)
AGENTS: dict[str, dict[str, Any]] = {
    "frontend": _agent("frontend-developer", "../agents/front-end-dev.md"),
    "backend": _agent("backend-architect", "../agents/backend-architect.md"),
    "cloud": _agent("cloud-architect", "../agents/cloud-architect.md"),
    "full-stack": _composite_agent("full-stack", ["backend", "frontend"]),
}


# ==============================================================================
# SPECIAL AGENTS
# ==============================================================================

# Splitter agent for task decomposition
SPLITTER_AGENT: dict[str, str] = _agent("splitter-agent", "../agents/splitter-agent.md")

# Prompt engineer agent
PROMPT_ENGINEER_AGENT: dict[str, str] = _agent("prompt-engineer", "../agents/prompt-engineer.md")

# Composer agent for multi-agent integration validation
COMPOSER_AGENT: dict[str, str] = _agent("composer", "../agents/composer.md")


# ==============================================================================
# ADDITIONAL SPECIALIST AGENTS
# ==============================================================================

ADDITIONAL_AGENTS: dict[str, dict[str, str]] = {
    "code-reviewer": _agent("code-reviewer", "../agents/code-reviewer.md"),
    "python-pro": _agent("python-pro", "../agents/python-pro.md"),
    "ui-ux-designer": _agent("ui-ux-designer", "../agents/ui-ux-designer.md"),
    "security-engineer": _agent("security-engineer", "../agents/security-engineer.md"),
    "ai-engineer": _agent("ai-engineer", "../agents/ai-engineer.md"),
    "data-engineer": _agent("data-engineer", "../agents/data-engineer.md"),
    "deployment-engineer": _agent("deployment-engineer", "../agents/deployment-engineer.md"),
    "composer": _agent("composer", "../agents/composer.md"),
}


# ==============================================================================
# CUSTOM AGENTS DISCOVERY
# ==============================================================================

# Cache for custom agents (loaded once)
_custom_agents_cache: dict[str, dict[str, Any]] | None = None


def _discover_custom_agents() -> dict[str, dict[str, Any]]:
    """
    Discover custom agents from the user's custom agents directory.
    
    Scans the custom agents directory for .md files and creates
    agent configurations for each one.
    
    Returns:
        Dictionary of agent_name -> agent_config.
    """
    custom_agents: dict[str, dict[str, Any]] = {}
    
    custom_dir = get_custom_agents_dir()
    if not custom_dir:
        return custom_agents
    
    logger.info(f"Loading custom agents from: {custom_dir}")
    
    for agent_file in custom_dir.glob("*.md"):
        # Skip hidden files and non-agent files
        if agent_file.name.startswith("."):
            continue
        
        # Agent name is the filename without extension
        agent_name = agent_file.stem  # e.g., "my-custom-agent" from "my-custom-agent.md"
        
        # Skip if name conflicts with built-in agents
        if agent_name in AGENTS or agent_name in ADDITIONAL_AGENTS:
            logger.warning(
                f"Custom agent '{agent_name}' conflicts with built-in agent, skipping"
            )
            continue
        
        custom_agents[agent_name] = {
            "name": agent_name,
            "file": str(agent_file),  # Absolute path for custom agents
            "model": get_model(),
            "custom": True,  # Flag to identify custom agents
        }
        logger.info(f"Loaded custom agent: {agent_name}")
    
    return custom_agents


def get_custom_agents() -> dict[str, dict[str, Any]]:
    """
    Get all custom agents (cached).
    
    Returns:
        Dictionary of custom agent configurations.
    """
    global _custom_agents_cache
    
    if _custom_agents_cache is None:
        _custom_agents_cache = _discover_custom_agents()
    
    return _custom_agents_cache


def refresh_custom_agents() -> dict[str, dict[str, Any]]:
    """
    Refresh the custom agents cache.
    
    Call this to pick up newly added custom agents without restarting.
    
    Returns:
        Dictionary of custom agent configurations.
    """
    global _custom_agents_cache
    _custom_agents_cache = _discover_custom_agents()
    return _custom_agents_cache


# ==============================================================================
# AGENT LOOKUP
# ==============================================================================

def get_agent_config(agent_name: str) -> dict[str, Any] | None:
    """
    Look up agent configuration by name.

    Searches in order:
    1. Core agents (frontend, backend, cloud, full-stack)
    2. Additional agents (code-reviewer, python-pro, etc.)
    3. Custom user agents (~/.agent-squared/agents/)

    Args:
        agent_name: The agent name or key.

    Returns:
        Agent configuration dict or None if not found.
    """
    # Check main agents
    for key, agent in AGENTS.items():
        if agent["name"] == agent_name or key == agent_name:
            return agent

    # Check additional agents
    if agent_name in ADDITIONAL_AGENTS:
        return ADDITIONAL_AGENTS[agent_name]
    
    # Check custom agents
    custom_agents = get_custom_agents()
    if agent_name in custom_agents:
        return custom_agents[agent_name]

    return None


def get_all_agent_names() -> list[str]:
    """
    Get list of all available agent names.
    
    Includes core agents, additional agents, and custom agents.
    """
    all_agents = list(AGENTS.keys()) + list(ADDITIONAL_AGENTS.keys())
    
    # Add custom agents
    custom_agents = get_custom_agents()
    all_agents.extend(custom_agents.keys())
    
    return all_agents


def get_custom_agent_names() -> list[str]:
    """Get list of custom agent names only."""
    return list(get_custom_agents().keys())
