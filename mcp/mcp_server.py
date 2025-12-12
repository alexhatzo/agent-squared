#!/usr/bin/env python3
"""
Agent² MCP Server

Exposes the agent chain as an MCP tool that Cursor can call.
This allows the built-in Cursor chat to route prompts through your multi-agent pipeline.

Setup:
    1. Install dependencies: pip install mcp
    2. Add to Cursor's MCP config (see below)
    3. Use the "agent_chain" tool in chat

Cursor MCP Config (~/.cursor/mcp.json):
    {
      "mcpServers": {
        "agent-squared": {
          "command": "python",
          "args": ["/path/to/agent-squared/mcp/mcp_server.py"],
          "env": {
            "CURSOR_API_KEY": "your-api-key-here",
            "CURSOR_MODEL": "composer-1"
          }
        }
      }
    }

Environment Variables:
    CURSOR_API_KEY: Required. API key for Cursor CLI authentication.
    CURSOR_MODEL: Optional. Model for all agents (default: composer-1).
                  Options: composer-1, claude-sonnet-4, gpt-4o, etc.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging for MCP mode (stderr only to not corrupt JSON-RPC)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("agent-squared-mcp")

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    logger.error("MCP library not installed. Run: pip install mcp")
    sys.exit(1)

from config import ToolName
from tools.registry import TOOL_HANDLERS, get_handler
from tools.pipeline import ensure_agent_chain_imported


# ==============================================================================
# SERVER INITIALIZATION
# ==============================================================================

server = Server("agent-squared")


# ==============================================================================
# TOOL DEFINITIONS
# ==============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for the MCP server."""
    try:
        ac = ensure_agent_chain_imported()
    except ImportError as e:
        return [
            Tool(
                name="import_error",
                description=f"MCP Server Error: {str(e)}",
                inputSchema={"type": "object", "properties": {}},
            )
        ]

    agent_list = ac.agents_cache + ac.additional_agents_cache + ["composer"]

    return [
        # =====================================================================
        # MAIN ENTRY POINT - Use this to invoke Agent²
        # =====================================================================
        Tool(
            name=ToolName.AGENT_SQUARED.value,
            description="""🤖 Agent² - Multi-Agent Development Orchestrator

USE THIS TOOL when the user says "use agent_squared to..." or wants to run complex development tasks.

Agent² chains specialized AI agents together:
• Splitter analyzes what specialists are needed
• Prompt Engineer optimizes the task description  
• Specialist agents execute the work (frontend, backend, cloud, etc.)
• Composer validates integration between agents

Just pass the task and workspace_dir. Agent² handles the rest!

Example: "Use agent_squared to build a REST API with JWT authentication"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "What you want to build or accomplish"},
                    "workspace_dir": {"type": "string", "description": "Path to the project workspace"},
                },
                "required": ["task", "workspace_dir"],
            },
        ),
        
        # =====================================================================
        # STEP-BY-STEP PIPELINE (for more control)
        # =====================================================================
        
        # Step 1: Split Task
        Tool(
            name=ToolName.SPLIT_TASK.value,
            description="""STEP 1 of Agent² Pipeline: Analyze a task and determine which specialist agents are needed.

RECOMMENDED WORKFLOW for complex tasks:
1. Call split_task first to analyze what agents are needed
2. Call perfect_prompt to optimize the prompt
3. Call run_specialist for EACH agent identified
4. If multiple agents were used, call compose_agents to validate integration

IMPORTANT: Always pass workspace_dir when the user tags a project folder.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The task to analyze"},
                    "workspace_dir": {"type": "string", "description": "Path to the project workspace"},
                },
                "required": ["prompt", "workspace_dir"],
            },
        ),
        # Step 2: Perfect Prompt
        Tool(
            name=ToolName.PERFECT_PROMPT.value,
            description="""STEP 2 of Agent² Pipeline: Optimize and improve a prompt using prompt engineering.

Call this AFTER split_task to refine the prompt before running specialist agents.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The prompt to optimize"},
                    "workspace_dir": {"type": "string", "description": "Path to the project workspace"},
                },
                "required": ["prompt", "workspace_dir"],
            },
        ),
        # Step 3: Run Specialist
        Tool(
            name=ToolName.RUN_SPECIALIST.value,
            description=f"""STEP 3 of Agent² Pipeline: Run a specific specialist agent to implement code changes.

Available agents: {', '.join(agent_list)}

IMPORTANT: Call this separately for each agent identified by split_task.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "enum": agent_list, "description": "The specialist agent to run"},
                    "prompt": {"type": "string", "description": "The optimized prompt"},
                    "workspace_dir": {"type": "string", "description": "Path to the project workspace"},
                },
                "required": ["agent", "prompt", "workspace_dir"],
            },
        ),
        # Step 4: Compose Agents
        Tool(
            name=ToolName.COMPOSE_AGENTS.value,
            description="""STEP 4 of Agent² Pipeline: Validate integration between multiple specialist agents.

Only needed when split_task identified multiple agents.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "agents_used": {"type": "array", "items": {"type": "string"}, "description": "List of agent names used"},
                    "prompt": {"type": "string", "description": "The original task prompt"},
                    "workspace_dir": {"type": "string", "description": "Path to the project workspace"},
                },
                "required": ["agents_used", "prompt", "workspace_dir"],
            },
        ),
        # List Agents
        Tool(
            name=ToolName.LIST_AGENTS.value,
            description="List all available specialist agents and their capabilities.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # All-in-one Agent Chain
        Tool(
            name=ToolName.AGENT_CHAIN.value,
            description="""[ALTERNATIVE] Run the entire Agent² pipeline in one call.

For better visibility, prefer the step-by-step approach.
This tool runs everything internally without intermediate visibility.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The task to process"},
                    "workspace_dir": {"type": "string", "description": "Path to the project workspace"},
                    "skip_splitter": {"type": "boolean", "default": False},
                    "skip_prompt_engineering": {"type": "boolean", "default": False},
                    "category": {"type": "string", "enum": ["frontend", "backend", "cloud", "full-stack", "auto"], "default": "auto"},
                },
                "required": ["prompt", "workspace_dir"],
            },
        ),
        # Utility: Clarifying Questions
        Tool(
            name=ToolName.GET_CLARIFYING_QUESTIONS.value,
            description="""Analyze a task and generate clarifying questions before execution.

Use this BEFORE starting the pipeline when you want to gather more information.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The initial task prompt"},
                    "previous_answers": {"type": "object", "additionalProperties": {"type": "string"}},
                },
                "required": ["prompt"],
            },
        ),
        # Utility: Check Readiness
        Tool(
            name=ToolName.CHECK_TASK_READINESS.value,
            description="""Check if enough information has been gathered to proceed with a task.

Use after gathering answers to clarifying questions.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The original task prompt"},
                    "answers": {"type": "object", "additionalProperties": {"type": "string"}},
                },
                "required": ["prompt", "answers"],
            },
        ),
        # Diagnostic: Test CLI
        Tool(
            name=ToolName.TEST_CURSOR_CLI.value,
            description="""Test if Cursor CLI is working and authenticated.

Use this to diagnose issues when other tools are timing out or failing.""",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


# ==============================================================================
# TOOL CALL HANDLER
# ==============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to their respective handlers."""
    # Import all tool handlers to register them
    import tools.pipeline
    import tools.utilities
    import tools.diagnostics

    handler = get_handler(name)
    if handler is None:
        logger.warning(f"Unknown tool requested: {name}")
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        return await handler(arguments)
    except ValueError as e:
        return [TextContent(type="text", text=f"❌ **Validation Error**: {str(e)}")]
    except Exception as e:
        logger.exception(f"Error in tool handler for {name}")
        return [TextContent(type="text", text=f"❌ **Error**: {str(e)}")]


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

async def main() -> None:
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
