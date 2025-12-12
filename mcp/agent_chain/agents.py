"""
Agent definitions for Agent² system.

This module contains all agent configurations including:
- Core specialist agents (frontend, backend, cloud, full-stack)
- Additional specialist agents (code-reviewer, python-pro, etc.)
- Special agents (splitter, prompt-engineer, composer)
- Custom user agents (any .md files in agents/ folder not already mapped)

Model Configuration:
    All agents use the model specified by CURSOR_MODEL environment variable.
    Default is "composer-1" if not set.

Custom Agents:
    Users can add their own agents by placing .md files in the agents/ folder.
    Any .md file that isn't already mapped to a built-in agent will be
    automatically discovered as a custom agent.
    
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
# AGENTS DIRECTORY
# ==============================================================================

# Get the project's agents directory (mcp/agent_chain/agents.py -> agents/)
_CURRENT_FILE = Path(__file__)
_MCP_DIR = _CURRENT_FILE.parent.parent  # mcp/
_PROJECT_ROOT = _MCP_DIR.parent  # agent-squared/
AGENTS_DIR = _PROJECT_ROOT / "agents"


def get_custom_agents_dir() -> Path | None:
    """
    Get the directory for custom user agents.
    
    Returns:
        Path to agents directory, or None if it doesn't exist.
    """
    if AGENTS_DIR.exists() and AGENTS_DIR.is_dir():
        return AGENTS_DIR
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

# Files that are mapped to built-in agents (relative to agents/ folder)
_BUILTIN_AGENT_FILES = {
    "front-end-dev.md",
    "backend-architect.md",
    "cloud-architect.md",
    "splitter-agent.md",
    "prompt-engineer.md",
    "composer.md",
    "code-reviewer.md",
    "python-pro.md",
    "ui-ux-designer.md",
    "security-engineer.md",
    "ai-engineer.md",
    "data-engineer.md",
    "deployment-engineer.md",
}

# Cache for custom agents (loaded once)
_custom_agents_cache: dict[str, dict[str, Any]] | None = None


def _discover_custom_agents() -> dict[str, dict[str, Any]]:
    """
    Discover custom agents from the agents/ directory.
    
    Scans the agents directory for .md files that aren't already
    mapped to built-in agents.
    
    Returns:
        Dictionary of agent_name -> agent_config.
    """
    custom_agents: dict[str, dict[str, Any]] = {}
    
    agents_dir = get_custom_agents_dir()
    if not agents_dir:
        return custom_agents
    
    logger.info(f"Scanning for custom agents in: {agents_dir}")
    
    for agent_file in agents_dir.glob("*.md"):
        # Skip hidden files
        if agent_file.name.startswith("."):
            continue
        
        # Skip files that are mapped to built-in agents
        if agent_file.name in _BUILTIN_AGENT_FILES:
            continue
        
        # Agent name is the filename without extension
        agent_name = agent_file.stem  # e.g., "debugger" from "debugger.md"
        
        # Skip if name conflicts with built-in agent keys
        if agent_name in AGENTS or agent_name in ADDITIONAL_AGENTS:
            logger.warning(
                f"Custom agent '{agent_name}' conflicts with built-in agent key, skipping"
            )
            continue
        
        custom_agents[agent_name] = {
            "name": agent_name,
            "file": str(agent_file),  # Absolute path for custom agents
            "model": get_model(),
            "custom": True,  # Flag to identify custom agents
        }
        logger.info(f"Discovered custom agent: {agent_name}")
    
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
    3. Custom user agents (any .md in agents/ not already mapped)

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


# ==============================================================================
# AGENT DESCRIPTIONS (for splitter)
# ==============================================================================

# Built-in agent descriptions for the splitter to understand when to use each
_AGENT_DESCRIPTIONS: dict[str, str] = {
    "frontend": "UI components, React, styling, accessibility, client-side logic",
    "backend": "APIs, databases, server logic, microservices, data processing",
    "cloud": "Infrastructure, AWS, Kubernetes, Terraform, deployment, scaling",
    "code-reviewer": "Code quality, security, maintainability review",
    "python-pro": "Python optimization, advanced features, testing",
    "ui-ux-designer": "User research, wireframes, design systems, prototyping",
    "security-engineer": "Security audits, vulnerability assessment, secure coding",
    "ai-engineer": "Machine learning, AI models, LLM integration, data pipelines",
    "data-engineer": "Data pipelines, ETL, data warehousing, analytics",
    "deployment-engineer": "CI/CD, deployment automation, release management",
    "composer": "Multi-agent integration, validation, coordination",
}


def _extract_description_from_md(file_path: str) -> str | None:
    """
    Extract description from a markdown agent file.
    
    Looks for:
    1. YAML frontmatter 'description' field
    2. First non-empty line after frontmatter
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        
        content = path.read_text()
        lines = content.split("\n")
        
        # Check for YAML frontmatter
        if lines and lines[0].strip() == "---":
            in_frontmatter = True
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    in_frontmatter = False
                    # Get first non-empty line after frontmatter
                    for after_line in lines[i+1:]:
                        stripped = after_line.strip()
                        if stripped and not stripped.startswith("#"):
                            return stripped[:100]  # Limit length
                    break
                if in_frontmatter and line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip()
                    return desc[:100]
        
        # Fallback: first non-empty, non-header line
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                return stripped[:100]
        
        return None
    except Exception:
        return None


def get_all_agents_with_descriptions() -> list[tuple[str, str]]:
    """
    Get all agents with their descriptions for the splitter.
    
    Returns:
        List of (agent_name, description) tuples.
    """
    result: list[tuple[str, str]] = []
    
    # Core agents (skip composite like full-stack)
    for key, agent in AGENTS.items():
        if "file" in agent:  # Skip composite agents
            desc = _AGENT_DESCRIPTIONS.get(key, agent.get("name", key))
            result.append((key, desc))
    
    # Additional agents
    for key in ADDITIONAL_AGENTS:
        desc = _AGENT_DESCRIPTIONS.get(key, key)
        result.append((key, desc))
    
    # Custom agents - try to extract description from their .md file
    custom_agents = get_custom_agents()
    for key, agent in custom_agents.items():
        file_path = agent.get("file", "")
        desc = _extract_description_from_md(file_path)
        if not desc:
            desc = f"Custom agent: {key}"
        result.append((key, desc))
    
    return result
