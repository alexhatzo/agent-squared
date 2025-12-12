"""
Core agent execution functions for Agent² system.

This module provides the low-level functions for running cursor-agent CLI commands.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from config import DEFAULT_TIMEOUT, CURSOR_AGENT_PATHS

logger = logging.getLogger("agent-chain")

# MCP mode flag - when True, all output goes to stderr
_MCP_MODE = False


def set_mcp_mode(enabled: bool = True) -> None:
    """
    Enable or disable MCP mode.

    When enabled, all print output goes to stderr to prevent corrupting
    the MCP JSON-RPC protocol on stdout.

    Args:
        enabled: Whether to enable MCP mode.
    """
    global _MCP_MODE
    _MCP_MODE = enabled


def is_mcp_mode() -> bool:
    """Check if MCP mode is enabled."""
    return _MCP_MODE


def agent_print(*args, **kwargs) -> None:
    """Print wrapper that redirects to stderr when in MCP mode."""
    import sys
    if _MCP_MODE:
        kwargs["file"] = sys.stderr
    print(*args, **kwargs)


def find_cursor_agent() -> str:
    """
    Find the cursor-agent executable.

    Checks PATH first, then common installation locations.

    Returns:
        Path to cursor-agent executable.

    Raises:
        FileNotFoundError: If cursor-agent is not found.
    """
    import shutil
    
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


def run_cursor_agent_detailed(
    prompt: str,
    agent_context: str | None = None,
    model: str = "composer-1",
    print_output: bool = True,
    output_format: str = "text",
    workspace_dir: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verbose: bool = False,
) -> tuple[str, str, int]:
    """
    Run cursor agent CLI command with full details.

    Args:
        prompt: The prompt to send to the agent.
        agent_context: Optional context/instructions for the agent.
        model: Model to use (default: composer-1).
        print_output: Use --print flag for non-interactive mode.
        output_format: Output format (text, json, stream-json).
        workspace_dir: Directory to run the command from (for codebase context).
        timeout: Timeout in seconds (default: 600).
        verbose: Print debug info to stderr.

    Returns:
        Tuple of (stdout, stderr, return_code).
        - return_code -1: Timeout
        - return_code -2: Cursor agent not found
        - return_code -3: Other error
    """
    # Find cursor-agent executable
    try:
        cursor_agent_path = find_cursor_agent()
    except FileNotFoundError as e:
        return "", str(e), -2

    cmd = [cursor_agent_path]

    # Pass API key explicitly if set (in addition to env var)
    api_key = os.environ.get("CURSOR_API_KEY")
    if api_key:
        cmd.extend(["--api-key", api_key])

    # Build the full prompt with agent context
    full_prompt = prompt
    if agent_context:
        full_prompt = f"{agent_context}\n\nUser Request: {prompt}"

    if print_output:
        # Syntax per docs: cursor-agent -p "prompt" --output-format text
        cmd.extend(["-p", full_prompt])
        cmd.extend(["--output-format", output_format])
    else:
        # Interactive mode uses positional prompt
        cmd.append(full_prompt)

    cmd.extend(["--model", model])
    cmd.append("--force")  # Auto-approve commands

    if verbose:
        logger.debug(f"Running: cursor agent --api-key *** --print ... (timeout={timeout}s)")

    try:
        # Run from workspace directory so agent has access to codebase
        cwd = str(workspace_dir) if workspace_dir else None

        # Suppress stderr to avoid JSON parsing errors in MCP client
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )

        if result.returncode != 0 and verbose:
            logger.warning(f"Cursor agent returned code {result.returncode}")

        return result.stdout, "", result.returncode

    except subprocess.TimeoutExpired:
        error_msg = f"Agent execution timed out after {timeout} seconds"
        logger.error(error_msg)
        return "", error_msg, -1
    except FileNotFoundError:
        error_msg = "Cursor CLI not found. Is 'cursor' in PATH? Run: cursor --version"
        logger.error(error_msg)
        return "", error_msg, -2
    except Exception as e:
        error_msg = f"Error running cursor agent: {str(e)}"
        logger.exception(error_msg)
        return "", error_msg, -3


def run_cursor_agent(
    prompt: str,
    agent_context: str | None = None,
    model: str = "composer-1",
    print_output: bool = True,
    output_format: str = "text",
    workspace_dir: Path | None = None,
) -> str:
    """
    Run cursor agent CLI command (simplified version).

    This is a simplified wrapper around run_cursor_agent_detailed that
    only returns the stdout output.

    Args:
        prompt: The prompt to send to the agent.
        agent_context: Optional context/instructions for the agent.
        model: Model to use.
        print_output: Use --print flag for non-interactive mode.
        output_format: Output format (text, json, stream-json).
        workspace_dir: Directory to run the command from.

    Returns:
        Agent output as string (stdout only).
    """
    stdout, _stderr, _code = run_cursor_agent_detailed(
        prompt, agent_context, model, print_output, output_format, workspace_dir
    )
    return stdout


def load_agent_instructions(agent_file: str, workspace_dir: Path | None = None) -> str:
    """
    Load agent instructions from a markdown file.

    Handles frontmatter extraction (content between --- delimiters is skipped).

    Args:
        agent_file: Path to the agent instruction file (can be relative).
        workspace_dir: Optional workspace directory for resolving relative paths.

    Returns:
        The agent instructions as a string, or empty string on error.
    """
    try:
        file_path = Path(agent_file)
        # If relative path, resolve relative to workspace or script directory
        if not file_path.is_absolute():
            if workspace_dir:
                file_path = workspace_dir / file_path
            else:
                # Default: relative to this module's parent directory
                file_path = Path(__file__).parent.parent / file_path

        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            # Extract content after frontmatter
            if "---" in content:
                parts = content.split("---", 2)
                if len(parts) > 2:
                    return parts[2].strip()
            return content
    except Exception as e:
        logger.warning(f"Could not load agent file {agent_file}: {e}")
    return ""
