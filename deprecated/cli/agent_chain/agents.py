"""
Agent definitions for Agent² CLI.

This module contains all agent configurations including:
- Core specialist agents (frontend, backend, cloud, full-stack)
- Additional specialist agents (code-reviewer, python-pro, etc.)
- Special agents (splitter, prompt-engineer, composer)

Model Configuration:
    All agents use the model specified by CURSOR_MODEL environment variable.
    Default is "composer-1" if not set.
"""

from __future__ import annotations

from typing import Any

from agent_chain.config import get_model


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

# Core specialist agents - paths relative to project root (parent of cli/)
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
# AGENT LOOKUP
# ==============================================================================

def get_agent_config(agent_name: str) -> dict[str, Any] | None:
    """
    Look up agent configuration by name.

    Searches both main agents and additional agents.

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

    return None


def get_all_agent_names() -> list[str]:
    """Get list of all available agent names."""
    return list(AGENTS.keys()) + list(ADDITIONAL_AGENTS.keys())
