"""
Utility tool handlers for Agent² MCP Server.

Utility tools:
- run_agent_squared: Main entry point - explains usage and starts pipeline
- run_list_agents: List available agents
"""

from __future__ import annotations

from typing import Any

from mcp.types import TextContent

from config import ToolName, WORKSPACE_DIR
from tools.registry import register_tool
from tools.pipeline import ensure_agent_chain_imported
from utils.output import OutputBuilder
from utils.helpers import get_workspace


@register_tool(ToolName.AGENT_SQUARED)
async def run_agent_squared(args: dict[str, Any]) -> list[TextContent]:
    """
    Main entry point for Agent² - orchestrate multi-agent development workflows.
    
    This is the recommended way to invoke Agent². Just say:
    "Use agent_squared to [your task]"
    
    This tool kicks off the pipeline by analyzing the task with the Splitter agent.
    You'll then see the recommended agents and can proceed step by step.
    """
    ac = ensure_agent_chain_imported()
    
    task = args.get("task", "")
    workspace_dir = args.get("workspace_dir", "")
    
    # If no task provided, show help/intro
    if not task:
        output = OutputBuilder()
        output.header("🤖 Agent² - Multi-Agent Development Orchestrator", level=1)
        output.blank()
        output.add("Agent² chains specialized AI agents together for complex development tasks.")
        output.blank()
        
        output.header("How to Use")
        output.add('Just say: **"Use agent_squared to [describe your task]"**')
        output.blank()
        output.add("Examples:")
        output.bullet('"Use agent_squared to build a REST API with authentication"')
        output.bullet('"Use agent_squared to create a React dashboard with charts"')
        output.bullet('"Use agent_squared to set up a CI/CD pipeline for AWS"')
        output.blank()
        
        output.header("How It Works")
        output.add("```")
        output.add("Your Task → Splitter → Prompt Engineer → Specialist Agent(s) → Composer")
        output.add("              ↓              ↓                    ↓              ↓")
        output.add("        Decompose      Optimize prompt      Execute work    Validate")
        output.add("```")
        output.blank()
        
        output.header("Available Specialists")
        specialists = []
        for key in ac.agents_cache:
            specialists.append(f"`{key}`")
        for key in ac.additional_agents_cache:
            specialists.append(f"`{key}`")
        output.add(", ".join(specialists))
        output.blank()
        
        output.separator()
        output.add("**Ready to start?** Just describe your task above!")
        
        return [TextContent(type="text", text=output.build())]
    
    # If task provided, start the chain by calling split_task
    # This gives visibility into the process - Cursor will see the results
    # and can then call perfect_prompt, run_specialist, etc.
    from tools.pipeline import run_split_task
    
    # Call split_task to analyze the task and recommend agents
    split_args = {
        "prompt": task,
        "workspace_dir": workspace_dir,
    }
    
    # Get split_task results
    split_results = await run_split_task(split_args)
    
    # Enhance the output with next steps guidance
    output = OutputBuilder()
    output.header("🤖 Agent² Pipeline Started", level=1)
    output.blank()
    output.add(f"**Task:** {task}")
    output.blank()
    
    # Include the split_task results
    if split_results and len(split_results) > 0:
        output.add(split_results[0].text)
    
    output.blank()
    output.separator()
    output.header("Recommended Next Steps", level=2)
    output.numbered(1, "Call `perfect_prompt` to optimize the task description")
    output.numbered(2, "Call `run_specialist` for each agent identified above")
    output.numbered(3, "If multiple agents were used, call `compose_agents` to validate integration")
    output.blank()
    output.add("**Tip:** The agents identified above should match your available specialists:")
    output.add(f"`{', '.join(ac.agents_cache + ac.additional_agents_cache)}`")
    
    return [TextContent(type="text", text=output.build())]


@register_tool(ToolName.LIST_AGENTS)
async def run_list_agents(args: dict[str, Any]) -> list[TextContent]:
    """List all available specialist agents and their capabilities."""
    from agent_chain import get_custom_agents, get_custom_agents_dir
    
    ac = ensure_agent_chain_imported()

    output = OutputBuilder()
    output.header("Core Agents")
    output.blank()
    for key, agent in ac.AGENTS.items():
        if "agents" not in agent:  # Skip composite agents
            output.bullet(f"**{key}** ({agent['name']})")

    output.blank()
    output.header("Additional Agents")
    output.blank()
    for key, agent in ac.ADDITIONAL_AGENTS.items():
        output.bullet(f"**{key}** ({agent['name']})")
    
    # Show custom agents
    custom_agents = get_custom_agents()
    if custom_agents:
        output.blank()
        output.header("Custom Agents")
        output.blank()
        for key, agent in custom_agents.items():
            output.bullet(f"**{key}** (custom)")
    
    # Show how to add custom agents
    output.blank()
    output.separator()
    output.header("Adding Custom Agents", level=3)
    custom_dir = get_custom_agents_dir()
    if custom_dir:
        output.add(f"Add `.md` files to: `{custom_dir}`")
        output.add("Any `.md` file not already mapped to a built-in agent will be auto-discovered.")

    return [TextContent(type="text", text=output.build())]
