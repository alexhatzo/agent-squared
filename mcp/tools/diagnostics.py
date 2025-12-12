"""
Diagnostic tool handlers for Agent² MCP Server.

Diagnostic tools:
- run_test_cursor_mcp: Test MCP server and Cursor CLI connectivity
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from typing import Any

from mcp.types import TextContent

from config import ToolName, WORKSPACE_DIR
from tools.registry import register_tool
from utils.output import OutputBuilder
from utils.helpers import mask_api_key, find_cursor_agent, get_mcp_config_example, truncate_output

logger = logging.getLogger("agent-squared-mcp")


@register_tool(ToolName.TEST_CURSOR_MCP)
async def run_test_cursor_mcp(args: dict[str, Any]) -> list[TextContent]:
    """Test if the MCP server is properly configured and Cursor CLI is working."""
    from config import get_model
    
    output = OutputBuilder()
    output.header("Agent² MCP Diagnostic")
    output.blank()

    # Show configured model
    model = get_model()
    output.add(f"**Model**: `{model}` (set via CURSOR_MODEL env var)")
    output.blank()

    # Check for CURSOR_API_KEY environment variable
    api_key = os.environ.get("CURSOR_API_KEY")
    if api_key:
        output.add(f"✅ CURSOR_API_KEY is set: `{mask_api_key(api_key)}`")
        output.blank()
    else:
        output.add("❌ CURSOR_API_KEY environment variable not set")
        output.blank()
        output.add("**To fix this:**")
        output.numbered(1, "Generate an API key from Cursor Settings")
        output.numbered(2, "Add it to your MCP config in `~/.cursor/mcp.json`:")
        output.code(get_mcp_config_example(), language="json")
        output.numbered(3, "Restart Cursor to reload the MCP server")
        return [TextContent(type="text", text=output.build())]

    # Find cursor-agent executable
    try:
        cursor_agent_path = find_cursor_agent()
        output.add(f"✅ cursor-agent found: `{cursor_agent_path}`")
        output.blank()
    except FileNotFoundError:
        output.add("❌ cursor-agent not found in PATH or common locations")
        output.blank()
        output.add("**To fix:**")
        output.numbered(1, "Install Cursor CLI: `curl https://cursor.com/install -fsS | bash`")
        output.numbered(2, "Make sure `cursor-agent` is in your PATH")
        return [TextContent(type="text", text=output.build())]

    # Test cursor-agent version
    version_info = await _test_cursor_version(cursor_agent_path)
    output.add(version_info)
    output.blank()

    # Test a simple agent call
    output.header("Testing Agent Call (30s timeout)...", level=3)
    output.blank()

    test_result = await _test_cursor_agent_call(cursor_agent_path, api_key)
    output.add(test_result)

    return [TextContent(type="text", text=output.build())]


async def _test_cursor_version(cursor_agent_path: str) -> str:
    """Test cursor-agent --version command."""
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [cursor_agent_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return f"✅ Version: `{result.stdout.strip()}`"
        else:
            error_info = [f"⚠️ Version check returned code {result.returncode}"]
            if result.stderr:
                error_info.append(f"   stderr: {result.stderr[:200]}")
            return "\n".join(error_info)
    except subprocess.TimeoutExpired:
        return "⚠️ Version check timed out"
    except Exception as e:
        return f"⚠️ Version check error: {e}"


async def _test_cursor_agent_call(cursor_agent_path: str, api_key: str | None) -> str:
    """Test a simple cursor-agent call."""
    # Build command
    test_cmd = [cursor_agent_path]
    if api_key:
        test_cmd.extend(["--api-key", api_key])
    test_cmd.extend(["-p", "Say hello", "--output-format", "text", "--force"])

    # Display command with masked API key
    display_cmd = test_cmd.copy()
    if api_key:
        api_key_idx = display_cmd.index("--api-key") + 1
        display_cmd[api_key_idx] = "***"

    result_lines = [
        f"**Command:** `{' '.join(display_cmd)}`",
        f"**Working dir:** `{WORKSPACE_DIR}`",
        "",
        "**Environment:**",
        f"- CURSOR_API_KEY: {'set' if api_key else 'NOT SET'}",
        f"- HOME: {os.environ.get('HOME', 'not set')}",
        "",
    ]

    try:
        start_time = time.time()
        env = os.environ.copy()

        process = subprocess.Popen(
            test_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(WORKSPACE_DIR),
            env=env,
        )

        try:
            stdout, stderr = process.communicate(timeout=30)
            elapsed = time.time() - start_time

            result_lines.append(f"**Completed in:** {elapsed:.1f}s")
            result_lines.append(f"**Return code:** {process.returncode}")
            result_lines.append("")

            if process.returncode == 0:
                output_preview = truncate_output(stdout, 500, "...")
                result_lines.append("✅ Agent call succeeded!")
                result_lines.append(f"**Response:**\n```\n{output_preview}\n```")
            else:
                result_lines.append("❌ Agent call failed")
                if stdout:
                    result_lines.append(f"**Stdout:**\n```\n{stdout[:500]}\n```")
                if stderr:
                    result_lines.append(f"**Stderr:**\n```\n{stderr[:500]}\n```")

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            process.kill()
            stdout, stderr = process.communicate()

            result_lines.extend([
                f"⏱️ **Timeout after {elapsed:.1f}s**",
                "",
                "**Partial output:**",
                f"Stdout: `{stdout[:300] if stdout else '(empty)'}`",
                f"Stderr: `{stderr[:300] if stderr else '(empty)'}`",
                "",
                "**Possible causes:**",
                "1. Keychain access issue",
                "2. Network connectivity",
                "3. cursor-agent waiting for input",
            ])

    except FileNotFoundError:
        result_lines.append("❌ cursor-agent command not found")
    except Exception as e:
        result_lines.append(f"❌ Error: {type(e).__name__}: {e}")

    return "\n".join(result_lines)
