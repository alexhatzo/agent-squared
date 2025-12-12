"""
Configuration constants for Agent² CLI.

This module centralizes all configuration to make the codebase
easier to maintain and customize.

Environment Variables:
    CURSOR_API_KEY: API key for Cursor CLI authentication
    CURSOR_MODEL: Model to use for all agents (default: composer-1)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# ==============================================================================
# PATH CONFIGURATION
# ==============================================================================

# CLI directory (where this config lives)
# This points to the installed package location (agent_chain/), not the current working directory
CLI_DIR = Path(__file__).parent.resolve()

# Project root - used for development mode
# When installed as a package, this may not be the actual project root
# In development: CLI_DIR is cli/agent_chain/, so parent.parent is project root
# When installed: CLI_DIR is site-packages/agent_chain/, parent.parent may not be project root
PROJECT_ROOT = CLI_DIR.parent.parent if CLI_DIR.name == "agent_chain" else CLI_DIR.parent

def _find_agents_directory() -> Path:
    """
    Find the agents directory.
    
    Tries multiple strategies:
    1. Development mode: agents at project root (../../agents relative to agent_chain/)
    2. Installed editable mode: agents at project root (same as development)
    3. Installed regular mode: agents should be included in package or at project root
    
    Returns:
        Path to agents directory (may not exist).
    """
    # Strategy 1: Development mode - agents at project root
    # CLI_DIR is cli/agent_chain/, so ../../agents is project_root/agents
    agents_candidate = CLI_DIR.parent.parent / "agents"
    if agents_candidate.exists():
        return agents_candidate
    
    # Strategy 2: Check if agents are packaged with the CLI (in agent_chain/agents/)
    agents_candidate = CLI_DIR / "agents"
    if agents_candidate.exists():
        return agents_candidate
    
    # Strategy 3: Look for agents in parent directories (for editable installs)
    # This handles cases where the package is installed in editable mode
    current = CLI_DIR
    for _ in range(6):  # Check up to 6 levels up
        agents_candidate = current / "agents"
        if agents_candidate.exists():
            return agents_candidate
        current = current.parent
    
    # Strategy 4: Fallback to project root (may not exist when installed)
    return PROJECT_ROOT / "agents"


# Agents directory - resolved at module load time
AGENTS_DIR = _find_agents_directory()

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
# EXECUTION CONFIGURATION
# ==============================================================================

# Default timeout for agent execution (in seconds)
DEFAULT_TIMEOUT = 600

# Output truncation limits
MAX_OUTPUT_LENGTH = 5000


# ==============================================================================
# WORKSPACE CONFIGURATION
# ==============================================================================

def get_default_workspace() -> Path:
    """
    Get the default workspace directory (current working directory).
    
    Returns:
        Path to the current working directory.
    """
    return Path(os.getcwd()).resolve()


def validate_workspace(workspace_dir: Path) -> None:
    """
    Validate that a workspace directory is suitable for use.
    
    Checks:
    - Directory exists
    - Is actually a directory
    - Is not empty (has at least some files/subdirectories)
    - Has reasonable project indicators (optional but recommended)
    
    Args:
        workspace_dir: Path to validate.
        
    Raises:
        ValueError: If workspace is invalid.
        FileNotFoundError: If workspace doesn't exist.
        NotADirectoryError: If path is not a directory.
    """
    if not workspace_dir.exists():
        raise FileNotFoundError(
            f"Workspace directory does not exist: {workspace_dir}\n"
            f"Please ensure you're running the command from a valid project directory."
        )
    
    if not workspace_dir.is_dir():
        raise NotADirectoryError(
            f"Workspace path is not a directory: {workspace_dir}\n"
            f"Please provide a valid directory path."
        )
    
    # Check if directory is empty
    try:
        contents = list(workspace_dir.iterdir())
        if not contents:
            raise ValueError(
                f"Workspace directory is empty: {workspace_dir}\n"
                f"Please run the command from a directory containing your project files."
            )
    except PermissionError:
        # If we can't read the directory, that's also a problem
        raise PermissionError(
            f"Permission denied reading workspace directory: {workspace_dir}\n"
            f"Please check directory permissions."
        )
    
    # Optional: Check for common project indicators (not required, but helpful)
    # This is a soft check - we don't fail if these don't exist
    common_indicators = [
        ".git",  # Git repository
        "package.json",  # Node.js project
        "requirements.txt",  # Python project
        "pyproject.toml",  # Python project
        "setup.py",  # Python project
        "Cargo.toml",  # Rust project
        "go.mod",  # Go project
        "pom.xml",  # Java/Maven project
        "build.gradle",  # Java/Gradle project
        "Makefile",  # Common build file
        "CMakeLists.txt",  # C/C++ project
    ]
    
    has_indicators = any((workspace_dir / indicator).exists() for indicator in common_indicators)
    
    if not has_indicators:
        # Warn but don't fail - user might have a valid project without these
        import sys
        print(
            f"⚠️  Warning: Workspace directory '{workspace_dir}' doesn't appear to contain "
            f"common project files.\n"
            f"   Make sure you're running from the correct directory.\n",
            file=sys.stderr
        )
