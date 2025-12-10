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
      "args": ["/path/to/agent-squared/mcp_server.py"],
      "env": {}
    }
  }
}
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP library not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Import from agent-chain
from agent_chain import (
    split_task,
    perfect_prompt,
    execute_agent,
    compose_integration,
    generate_clarification_questions,
    has_enough_info,
    load_agent_instructions,
    run_cursor_agent_detailed,
    AGENTS,
    ADDITIONAL_AGENTS,
    SPLITTER_AGENT,
    PROMPT_ENGINEER_AGENT,
    COMPOSER_AGENT,
)

# MCP-specific timeout (shorter than CLI default)
MCP_TIMEOUT = 90  # 90 seconds max per agent call


async def run_with_timeout_and_errors(func, *args, timeout_msg: str = "Operation", **kwargs):
    """
    Wrapper to run agent functions with timeout handling and error reporting.
    
    Returns:
        Tuple of (result, error_message) - error_message is None on success
    """
    import concurrent.futures
    
    try:
        # Run in thread pool with timeout
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = loop.run_in_executor(pool, lambda: func(*args, **kwargs))
            result = await asyncio.wait_for(future, timeout=MCP_TIMEOUT)
            return result, None
    except asyncio.TimeoutError:
        return None, f"⏱️ **Timeout**: {timeout_msg} took longer than {MCP_TIMEOUT} seconds. The Cursor CLI may be waiting for authentication or input."
    except Exception as e:
        return None, f"❌ **Error**: {str(e)}"

# Initialize MCP server
server = Server("agent-squared")

# Workspace directory (where agent-squared lives)
WORKSPACE_DIR = Path(__file__).parent.resolve()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="agent_chain",
            description="""Route a prompt through the Agent² multi-agent pipeline.
            
The pipeline:
1. Splitter Agent - Analyzes prompt, determines which specialists needed
2. Prompt Engineer - Optimizes and perfects the prompt  
3. Specialist Agent(s) - Execute the task (frontend, backend, cloud, etc.)
4. Composer Agent - Validates integration when multiple agents are used

Use this for complex tasks that benefit from decomposition and specialized expertise.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The task or question to process through the agent chain"
                    },
                    "skip_splitter": {
                        "type": "boolean",
                        "description": "Skip task decomposition (default: false)",
                        "default": False
                    },
                    "skip_prompt_engineering": {
                        "type": "boolean",
                        "description": "Skip prompt optimization (default: false)",
                        "default": False
                    },
                    "category": {
                        "type": "string",
                        "enum": ["frontend", "backend", "cloud", "full-stack", "auto"],
                        "description": "Force a specific agent category (default: auto-detect)",
                        "default": "auto"
                    }
                },
                "required": ["prompt"]
            }
        ),
        Tool(
            name="split_task",
            description="Analyze a prompt and determine which specialist agents are needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The task to analyze"
                    }
                },
                "required": ["prompt"]
            }
        ),
        Tool(
            name="perfect_prompt",
            description="Optimize and improve a prompt using prompt engineering techniques.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to optimize"
                    }
                },
                "required": ["prompt"]
            }
        ),
        Tool(
            name="list_agents",
            description="List all available specialist agents and their capabilities.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="run_specialist",
            description="Run a specific specialist agent directly (bypasses splitter/prompt engineer).",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "string",
                        "enum": list(AGENTS.keys()) + list(ADDITIONAL_AGENTS.keys()) + ["composer"],
                        "description": "The specialist agent to run"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The task for the agent"
                    }
                },
                "required": ["agent", "prompt"]
            }
        ),
        Tool(
            name="get_clarifying_questions",
            description="""Analyze a task and generate clarifying questions before execution.
            
Use this BEFORE agent_chain when you want to gather more information from the user.
Returns questions that should be answered to improve task execution.

Workflow:
1. Call get_clarifying_questions with the initial prompt
2. Ask the user the returned questions
3. Call agent_chain with the enriched prompt including their answers
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The initial task/prompt to analyze"
                    },
                    "previous_answers": {
                        "type": "object",
                        "description": "Optional: Previous Q&A pairs if iterating",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["prompt"]
            }
        ),
        Tool(
            name="check_task_readiness",
            description="""Check if enough information has been gathered to proceed with a task.
            
Use this after gathering answers to clarifying questions to determine if you should:
- Proceed with agent_chain (if ready)
- Ask more questions (if not ready)
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The original task prompt"
                    },
                    "answers": {
                        "type": "object",
                        "description": "Dictionary of question → answer pairs gathered so far",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["prompt", "answers"]
            }
        ),
        Tool(
            name="test_cursor_cli",
            description="""Test if Cursor CLI is working and authenticated.
            
Use this to diagnose issues when other tools are timing out or failing.
Returns status of Cursor CLI connectivity.
            """,
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "agent_chain":
        return await run_agent_chain(arguments)
    elif name == "split_task":
        return await run_split_task(arguments)
    elif name == "perfect_prompt":
        return await run_perfect_prompt(arguments)
    elif name == "list_agents":
        return await run_list_agents()
    elif name == "run_specialist":
        return await run_specialist(arguments)
    elif name == "get_clarifying_questions":
        return await run_get_clarifying_questions(arguments)
    elif name == "check_task_readiness":
        return await run_check_task_readiness(arguments)
    elif name == "test_cursor_cli":
        return await run_test_cursor_cli()
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run_agent_chain(args: dict) -> list[TextContent]:
    """Run the full agent chain pipeline."""
    prompt = args.get("prompt", "")
    skip_splitter = args.get("skip_splitter", False)
    skip_prompt_engineering = args.get("skip_prompt_engineering", False)
    category = args.get("category", "auto")
    
    results = []
    results.append(f"🔗 **Agent² Pipeline Started**\n")
    results.append(f"📝 Input: {prompt}\n")
    
    # Phase 0: Splitter
    splitter_result = None
    if not skip_splitter and category == "auto":
        results.append("\n---\n## Phase 0: Task Decomposition\n")
        splitter_result = await asyncio.to_thread(split_task, prompt, WORKSPACE_DIR)
        results.append(f"- Requires multiple agents: {splitter_result.get('requires_multiple_agents', False)}")
        results.append(f"- Agents needed: {', '.join(splitter_result.get('agents_needed', []))}")
        results.append(f"- Strategy: {splitter_result.get('execution_strategy', 'sequential')}")
        results.append(f"- Summary: {splitter_result.get('summary', 'N/A')}\n")
    
    # Phase 1: Prompt Engineering
    perfected = prompt
    detected_category = category if category != "auto" else "other"
    
    if not skip_prompt_engineering:
        results.append("\n---\n## Phase 1: Prompt Engineering\n")
        perfected, detected_category = await asyncio.to_thread(perfect_prompt, prompt, WORKSPACE_DIR)
        results.append(f"**Optimized prompt:** {perfected[:500]}{'...' if len(perfected) > 500 else ''}\n")
        results.append(f"**Category:** {detected_category}\n")
    
    # Phase 2: Specialist Execution
    results.append("\n---\n## Phase 2: Specialist Execution\n")
    
    agents_used = []
    
    if splitter_result and splitter_result.get("requires_multiple_agents"):
        for agent_plan in splitter_result.get("execution_order", []):
            agent_name = agent_plan.get("agent", "")
            agent_focus = agent_plan.get("focus", "")
            agents_used.append(agent_name)
            results.append(f"\n### Agent: {agent_name}\n")
            results.append(f"Focus: {agent_focus}\n")
            
            output = await asyncio.to_thread(
                execute_agent, agent_name, perfected, agent_focus, False, WORKSPACE_DIR
            )
            results.append(f"\n{output}\n")
    else:
        # Single agent execution
        agents_used.append(detected_category)
        results.append(f"\n### Agent: {detected_category}\n")
        output = await asyncio.to_thread(
            execute_agent, detected_category, perfected, "", False, WORKSPACE_DIR
        )
        results.append(f"\n{output}\n")
    
    # Phase 3: Composer (only when multiple agents were used)
    if len(agents_used) > 1:
        results.append("\n---\n## Phase 3: Integration Validation (Composer)\n")
        results.append(f"Validating integration between: {', '.join(agents_used)}\n")
        
        composer_output = await asyncio.to_thread(
            compose_integration, agents_used, perfected, False, WORKSPACE_DIR
        )
        results.append(f"\n{composer_output}\n")
    
    results.append("\n---\n✅ **Agent² Pipeline Complete**")
    
    return [TextContent(type="text", text="\n".join(results))]


async def run_split_task(args: dict) -> list[TextContent]:
    """Run just the splitter agent."""
    prompt = args.get("prompt", "")
    
    result, error = await run_with_timeout_and_errors(
        split_task, prompt, WORKSPACE_DIR,
        timeout_msg="Task splitting"
    )
    
    if error:
        return [TextContent(type="text", text=error)]
    
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def run_perfect_prompt(args: dict) -> list[TextContent]:
    """Run just the prompt engineer."""
    prompt = args.get("prompt", "")
    
    result, error = await run_with_timeout_and_errors(
        perfect_prompt, prompt, WORKSPACE_DIR,
        timeout_msg="Prompt engineering"
    )
    
    if error:
        return [TextContent(type="text", text=error)]
    
    perfected, category = result
    return [TextContent(
        type="text", 
        text=f"**Perfected Prompt:**\n{perfected}\n\n**Category:** {category}"
    )]


async def run_list_agents() -> list[TextContent]:
    """List all available agents."""
    agents_info = []
    agents_info.append("## Core Agents\n")
    for key, agent in AGENTS.items():
        if "agents" not in agent:  # Skip composite agents
            agents_info.append(f"- **{key}** ({agent['name']})")
    
    agents_info.append("\n## Additional Agents\n")
    for key, agent in ADDITIONAL_AGENTS.items():
        agents_info.append(f"- **{key}** ({agent['name']})")
    
    return [TextContent(type="text", text="\n".join(agents_info))]


async def run_specialist(args: dict) -> list[TextContent]:
    """Run a specific specialist agent."""
    agent = args.get("agent", "")
    prompt = args.get("prompt", "")
    
    output = await asyncio.to_thread(execute_agent, agent, prompt, "", False, WORKSPACE_DIR)
    return [TextContent(type="text", text=output)]


async def run_get_clarifying_questions(args: dict) -> list[TextContent]:
    """Generate clarifying questions for a task."""
    prompt = args.get("prompt", "")
    previous_answers = args.get("previous_answers", {})
    
    result, error = await run_with_timeout_and_errors(
        generate_clarification_questions,
        prompt,
        previous_answers if previous_answers else None,
        WORKSPACE_DIR,
        timeout_msg="Generating clarifying questions"
    )
    
    if error:
        return [TextContent(
            type="text",
            text=f"{error}\n\n**Troubleshooting:**\n"
                 "1. Check if Cursor CLI is authenticated: `cursor auth status`\n"
                 "2. Try running manually: `cursor agent --print 'test'`\n"
                 "3. The CLI may need to complete an interactive setup first"
        )]
    
    questions, analysis = result
    
    if not questions:
        return [TextContent(
            type="text",
            text="✅ **No clarification needed.** The prompt is clear enough to proceed.\n\n"
                 f"**Analysis:** {analysis}\n\n"
                 "You can now call `agent_chain` with this prompt."
        )]
    
    output = ["## Clarifying Questions\n"]
    output.append("Please ask the user these questions before proceeding:\n")
    for i, q in enumerate(questions, 1):
        output.append(f"{i}. {q}")
    
    if analysis:
        output.append(f"\n**Why these questions matter:** {analysis}")
    
    output.append("\n---")
    output.append("After getting answers, either:")
    output.append("- Call `check_task_readiness` to verify enough info")
    output.append("- Call `agent_chain` with the enriched prompt")
    
    return [TextContent(type="text", text="\n".join(output))]


async def run_check_task_readiness(args: dict) -> list[TextContent]:
    """Check if enough information has been gathered."""
    prompt = args.get("prompt", "")
    answers = args.get("answers", {})
    
    if not answers:
        return [TextContent(
            type="text",
            text="⚠️ No answers provided. Call `get_clarifying_questions` first, "
                 "then gather answers from the user."
        )]
    
    is_ready, error = await run_with_timeout_and_errors(
        has_enough_info, prompt, answers, WORKSPACE_DIR,
        timeout_msg="Checking task readiness"
    )
    
    if error:
        return [TextContent(type="text", text=error)]
    
    if is_ready:
        # Build the enriched prompt
        enriched = prompt + "\n\n### Additional Context:\n"
        for q, a in answers.items():
            enriched += f"- {q}: {a}\n"
        
        return [TextContent(
            type="text",
            text="✅ **Ready to proceed!**\n\n"
                 "Enough information has been gathered. Call `agent_chain` with this enriched prompt:\n\n"
                 f"```\n{enriched}\n```"
        )]
    else:
        return [TextContent(
            type="text",
            text="⚠️ **More information needed.**\n\n"
                 "Consider asking more questions or proceeding with what you have.\n\n"
                 "Call `get_clarifying_questions` again with the current answers to get follow-up questions, "
                 "or call `agent_chain` if you want to proceed anyway."
        )]


async def run_test_cursor_cli() -> list[TextContent]:
    """Test if Cursor CLI is working."""
    import subprocess
    import shutil
    
    results = ["## Cursor CLI Diagnostic\n"]
    
    # Check if cursor command exists
    cursor_path = shutil.which("cursor")
    if cursor_path:
        results.append(f"✅ Cursor CLI found: `{cursor_path}`\n")
    else:
        results.append("❌ Cursor CLI not found in PATH\n")
        results.append("**Fix:** Make sure Cursor is installed and `cursor` command is in your PATH\n")
        return [TextContent(type="text", text="\n".join(results))]
    
    # Test cursor version
    try:
        version_result = subprocess.run(
            ["cursor", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if version_result.returncode == 0:
            results.append(f"✅ Version: `{version_result.stdout.strip()}`\n")
        else:
            results.append(f"⚠️ Version check failed: {version_result.stderr}\n")
    except subprocess.TimeoutExpired:
        results.append("⚠️ Version check timed out\n")
    except Exception as e:
        results.append(f"⚠️ Version check error: {e}\n")
    
    # Test a simple agent call with short timeout
    results.append("\n### Testing Agent Call (15s timeout)...\n")
    try:
        test_result = subprocess.run(
            ["cursor", "agent", "--print", "--output-format", "text", "--force", "Say hello"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(WORKSPACE_DIR)
        )
        
        if test_result.returncode == 0:
            output_preview = test_result.stdout[:200] + "..." if len(test_result.stdout) > 200 else test_result.stdout
            results.append(f"✅ Agent call succeeded!\n")
            results.append(f"**Response preview:** {output_preview}\n")
        else:
            results.append(f"❌ Agent call failed (code {test_result.returncode})\n")
            if test_result.stderr:
                results.append(f"**Error:** {test_result.stderr[:300]}\n")
            results.append("\n**Possible issues:**\n")
            results.append("- Cursor may need authentication: run `cursor auth login`\n")
            results.append("- Check if Cursor app is running\n")
            results.append("- Try running manually: `cursor agent --print 'test'`\n")
            
    except subprocess.TimeoutExpired:
        results.append("⏱️ **Timeout**: Agent call took longer than 15 seconds\n")
        results.append("\n**This usually means:**\n")
        results.append("- Cursor CLI is waiting for authentication\n")
        results.append("- Try running `cursor auth login` in terminal first\n")
        results.append("- Or run `cursor agent --print 'test'` to see what it's waiting for\n")
    except Exception as e:
        results.append(f"❌ Error: {e}\n")
    
    return [TextContent(type="text", text="\n".join(results))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

