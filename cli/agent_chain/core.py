"""
Core agent execution functions for Agent² CLI.

This module provides the low-level functions for running cursor-agent CLI commands.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from agent_chain.config import DEFAULT_TIMEOUT, CURSOR_AGENT_PATHS, AGENTS_DIR, CLI_DIR


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
        print_output: Use -p flag for non-interactive mode.
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
        print(f"[DEBUG] Running: cursor-agent --api-key *** -p ... (timeout={timeout}s)", file=sys.stderr)

    try:
        # Run from workspace directory so agent has access to codebase
        cwd = str(workspace_dir) if workspace_dir else None

        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )

        if result.returncode != 0:
            if verbose or result.stderr:
                print(f"Error running cursor agent (code {result.returncode}): {result.stderr}", file=sys.stderr)

        return result.stdout, result.stderr, result.returncode

    except subprocess.TimeoutExpired:
        error_msg = f"Agent execution timed out after {timeout} seconds"
        print(f"Error: {error_msg}", file=sys.stderr)
        return "", error_msg, -1
    except FileNotFoundError:
        error_msg = "Cursor CLI not found. Is 'cursor-agent' in PATH? Run: cursor --version"
        print(f"Error: {error_msg}", file=sys.stderr)
        return "", error_msg, -2
    except Exception as e:
        error_msg = f"Error running cursor agent: {str(e)}"
        print(f"Error: {error_msg}", file=sys.stderr)
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
        print_output: Use -p flag for non-interactive mode.
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

    Agent files are resolved relative to the CLI installation location (not the workspace),
    so they work regardless of where the command is run from.

    Args:
        agent_file: Path to the agent instruction file (can be relative).
                   Relative paths like "../agents/front-end-dev.md" are resolved
                   relative to the CLI installation location.
        workspace_dir: Optional workspace directory (not used for path resolution,
                      but kept for backward compatibility).

    Returns:
        The agent instructions as a string, or empty string on error.
    """
    try:
        file_path = Path(agent_file)
        
        # If absolute path, use as-is
        if file_path.is_absolute():
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                # Extract content after frontmatter
                if "---" in content:
                    parts = content.split("---", 2)
                    if len(parts) > 2:
                        return parts[2].strip()
                return content
            return ""
        
        # For relative paths, resolve relative to CLI installation location
        # Agent files should be found relative to the installed package, not workspace
        
        # Try multiple resolution strategies
        candidates = []
        
        # Strategy 1: Handle paths like "../agents/front-end-dev.md"
        # Resolve relative to CLI_DIR's parent (project root in development)
        if agent_file.startswith("../"):
            relative_path = agent_file[3:]  # Remove "../"
            # If path starts with "agents/", extract just the filename
            if relative_path.startswith("agents/"):
                agent_name = relative_path[7:]  # Remove "agents/" prefix
                # Try AGENTS_DIR first (found at module load time)
                if AGENTS_DIR:
                    candidates.append(AGENTS_DIR / agent_name)
                # Also try relative to CLI_DIR parent
                candidates.append(CLI_DIR.parent / relative_path)
            else:
                candidates.append(CLI_DIR.parent / relative_path)
        
        # Strategy 2: Handle "./agents/file.md" or "agents/file.md"
        elif agent_file.startswith("./"):
            relative_path = agent_file[2:]
            candidates.append(CLI_DIR / relative_path)
            if AGENTS_DIR and relative_path.startswith("agents/"):
                agent_name = relative_path[7:]
                candidates.append(AGENTS_DIR / agent_name)
        
        # Strategy 3: Just a filename or path without prefix
        else:
            # Try in AGENTS_DIR if it's just a filename
            if "/" not in agent_file and AGENTS_DIR:
                candidates.append(AGENTS_DIR / agent_file)
            # Try relative to CLI_DIR
            candidates.append(CLI_DIR / agent_file)
            # Try relative to CLI_DIR parent
            candidates.append(CLI_DIR.parent / agent_file)
        
        # Try each candidate path
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                content = candidate.read_text(encoding="utf-8")
                # Extract content after frontmatter
                if "---" in content:
                    parts = content.split("---", 2)
                    if len(parts) > 2:
                        return parts[2].strip()
                return content
        
        # If none found, print warning with tried paths
        tried_paths = ", ".join(str(c) for c in candidates[:3])  # Show first 3
        print(
            f"Warning: Agent file not found: {agent_file}\n"
            f"  Tried: {tried_paths}",
            file=sys.stderr
        )
    except Exception as e:
        print(f"Warning: Could not load agent file {agent_file}: {e}", file=sys.stderr)
    return ""
