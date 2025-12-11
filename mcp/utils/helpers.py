"""
Helper utilities for Agent² MCP Server.

Common utility functions used across the codebase.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from config import CONFIG, CURSOR_AGENT_PATHS, WORKSPACE_DIR

logger = logging.getLogger("agent-squared")


def truncate_output(
    text: str,
    max_length: int,
    suffix: str = "\n\n... (output truncated)",
) -> str:
    """
    Truncate text to max_length, adding suffix if truncated.

    Args:
        text: The text to truncate.
        max_length: Maximum length before truncation.
        suffix: Text to append if truncated.

    Returns:
        Original text if shorter than max_length, otherwise truncated with suffix.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix


def get_modified_files(workspace_dir: Path) -> list[str]:
    """
    Get list of modified files using git diff.

    Args:
        workspace_dir: Path to the git repository.

    Returns:
        List of modified file paths, empty if git is unavailable or not a repo.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(workspace_dir),
            capture_output=True,
            text=True,
            timeout=CONFIG.git_timeout_seconds,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Could not get git diff: {e}")
    return []


def mask_api_key(api_key: str) -> str:
    """
    Mask API key for safe display, showing first 8 and last 4 characters.

    Args:
        api_key: The API key to mask.

    Returns:
        Masked API key string.
    """
    if len(api_key) > 12:
        return f"{api_key[:8]}...{api_key[-4:]}"
    return "****"


def find_cursor_agent() -> str:
    """
    Find the cursor-agent executable.

    Checks PATH first, then common installation locations.

    Returns:
        Path to cursor-agent executable.

    Raises:
        FileNotFoundError: If cursor-agent is not found.
    """
    # First try PATH
    cursor_agent_path = shutil.which("cursor-agent")
    if cursor_agent_path:
        return cursor_agent_path

    # Check common installation locations
    for path in CURSOR_AGENT_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    raise FileNotFoundError(
        "cursor-agent not found. Install with: curl https://cursor.com/install -fsS | bash"
    )


def get_mcp_config_example() -> str:
    """Return example MCP configuration JSON."""
    return """{
  "mcpServers": {
    "agent-squared": {
      "command": "python",
      "args": ["/path/to/mcp/mcp_server.py"],
      "env": {
        "CURSOR_API_KEY": "your-api-key-here",
        "CURSOR_MODEL": "composer-1"
      }
    }
  }
}"""


def get_workspace(args: dict, default: Path = WORKSPACE_DIR) -> Path:
    """
    Extract and validate workspace directory from tool arguments.

    Args:
        args: Tool arguments dictionary.
        default: Default workspace if not specified.

    Returns:
        Resolved Path to the workspace directory.

    Raises:
        ValueError: If the specified workspace does not exist.
    """
    workspace_dir_str = args.get("workspace_dir", "")
    if workspace_dir_str:
        workspace_dir = Path(workspace_dir_str).resolve()
        if not workspace_dir.exists():
            raise ValueError(f"Workspace directory does not exist: {workspace_dir}")
        return workspace_dir
    return default
