"""
Pipeline tool handlers for Agent² MCP Server.

Main pipeline tools:
- run_agent_chain: Full pipeline execution
- run_split_task: Task analysis (Step 1)
- run_perfect_prompt: Prompt optimization (Step 2)
- run_specialist: Specialist agent execution (Step 3)
- run_compose_agents: Integration validation (Step 4)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp.types import TextContent

from config import CONFIG, ToolName, WORKSPACE_DIR
from tools.registry import register_tool
from utils.output import OutputBuilder
from utils.helpers import get_workspace, get_modified_files, truncate_output

logger = logging.getLogger("agent-squared-mcp")


# ==============================================================================
# LAZY IMPORT MANAGEMENT
# ==============================================================================

@dataclass
class AgentChainModule:
    """Container for lazily-imported agent_chain module components."""

    imported: bool = False
    agents_cache: list[str] = field(default_factory=list)
    additional_agents_cache: list[str] = field(default_factory=list)

    # These will be set after import
    split_task: Any = None
    perfect_prompt: Any = None
    execute_agent: Any = None
    compose_integration: Any = None
    AGENTS: dict | None = None
    ADDITIONAL_AGENTS: dict | None = None


_agent_chain = AgentChainModule()


def ensure_agent_chain_imported() -> AgentChainModule:
    """Lazy import of agent_chain module to avoid startup delays."""
    if _agent_chain.imported:
        return _agent_chain

    try:
        from agent_chain import (
            split_task,
            perfect_prompt,
            execute_agent,
            compose_integration,
            set_mcp_mode,
            AGENTS,
            ADDITIONAL_AGENTS,
        )

        set_mcp_mode(True)

        _agent_chain.split_task = split_task
        _agent_chain.perfect_prompt = perfect_prompt
        _agent_chain.execute_agent = execute_agent
        _agent_chain.compose_integration = compose_integration
        _agent_chain.AGENTS = AGENTS
        _agent_chain.ADDITIONAL_AGENTS = ADDITIONAL_AGENTS
        
        # Filter out composite agents (those with "agents" key instead of "file")
        # These should be run via the full pipeline, not as individual specialists
        _agent_chain.agents_cache = [
            key for key, agent in AGENTS.items()
            if "file" in agent  # Only include agents with instruction files
        ]
        _agent_chain.additional_agents_cache = list(ADDITIONAL_AGENTS.keys())
        _agent_chain.imported = True

        logger.info("Agent chain module imported successfully")
        return _agent_chain

    except Exception as e:
        _agent_chain.imported = True
        error_msg = f"Failed to import agent_chain module: {e}"
        logger.error(error_msg)
        raise ImportError(error_msg) from e


# ==============================================================================
# ASYNC UTILITIES
# ==============================================================================

async def run_with_timeout(
    func: Any,
    *args: Any,
    timeout_msg: str = "Operation",
    timeout_seconds: int | None = None,
    **kwargs: Any,
) -> tuple[Any, str | None]:
    """Run a synchronous function in a thread pool with timeout handling."""
    timeout = timeout_seconds or CONFIG.timeout_seconds

    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: func(*args, **kwargs)),
            timeout=timeout,
        )
        return result, None
    except asyncio.TimeoutError:
        return None, (
            f"⏱️ **Timeout**: {timeout_msg} took longer than {timeout} seconds. "
            "The Cursor CLI may be waiting for authentication or input."
        )
    except Exception as e:
        logger.exception(f"Error in {timeout_msg}")
        return None, f"❌ **Error**: {str(e)}"


# ==============================================================================
# PIPELINE RESULT CONTAINER
# ==============================================================================

@dataclass
class PipelineResult:
    """Container for agent pipeline execution results."""

    agents_used: list[str] = field(default_factory=list)
    agent_outputs: list[dict[str, Any]] = field(default_factory=list)
    composer_output: str | None = None
    detected_category: str = "other"
    perfected_prompt: str = ""
    modified_files: list[str] = field(default_factory=list)


# ==============================================================================
# TOOL HANDLERS
# ==============================================================================

@register_tool(ToolName.AGENT_CHAIN)
async def run_agent_chain(args: dict[str, Any]) -> list[TextContent]:
    """Run the full agent chain pipeline with progress updates."""
    ac = ensure_agent_chain_imported()

    prompt = args.get("prompt", "")
    skip_splitter = args.get("skip_splitter", False)
    skip_prompt_engineering = args.get("skip_prompt_engineering", False)
    category = args.get("category", "auto")

    try:
        workspace_dir = get_workspace(args, WORKSPACE_DIR)
    except ValueError as e:
        return [TextContent(type="text", text=f"❌ **Error**: {str(e)}")]

    result = PipelineResult(perfected_prompt=prompt)
    result.detected_category = category if category != "auto" else "other"

    def log_progress(phase: str, message: str) -> None:
        logger.info(f"[{phase}] {message}")

    log_progress("START", f"Pipeline started for workspace: {workspace_dir}")

    # Phase 0: Splitter
    splitter_result = None
    if not skip_splitter and category == "auto":
        log_progress("PHASE 0", "Running task decomposition...")
        splitter_result = await asyncio.to_thread(ac.split_task, prompt, workspace_dir)
        log_progress("PHASE 0", f"Complete - Agents: {splitter_result.get('agents_needed', [])}")

    # Phase 1: Prompt Engineering
    if not skip_prompt_engineering:
        log_progress("PHASE 1", "Running prompt engineering...")
        result.perfected_prompt, result.detected_category = await asyncio.to_thread(
            ac.perfect_prompt, prompt, workspace_dir
        )
        log_progress("PHASE 1", f"Complete - Category: {result.detected_category}")

    # Phase 2: Specialist Execution
    log_progress("PHASE 2", "Starting specialist execution...")

    if splitter_result and splitter_result.get("requires_multiple_agents"):
        for i, agent_plan in enumerate(splitter_result.get("execution_order", []), 1):
            agent_name = agent_plan.get("agent", "")
            agent_focus = agent_plan.get("focus", "")
            result.agents_used.append(agent_name)

            log_progress("PHASE 2", f"Running agent {i}: {agent_name}...")
            output = await asyncio.to_thread(
                ac.execute_agent, agent_name, result.perfected_prompt, agent_focus, False, workspace_dir
            )
            result.agent_outputs.append({"agent": agent_name, "focus": agent_focus, "output": output})
    else:
        result.agents_used.append(result.detected_category)
        output = await asyncio.to_thread(
            ac.execute_agent, result.detected_category, result.perfected_prompt, "", False, workspace_dir
        )
        result.agent_outputs.append({"agent": result.detected_category, "focus": "", "output": output})

    # Phase 3: Composer
    if len(result.agents_used) > 1:
        log_progress("PHASE 3", "Running integration validation...")
        result.composer_output = await asyncio.to_thread(
            ac.compose_integration, result.agents_used, result.perfected_prompt, False, workspace_dir
        )

    log_progress("DONE", "Pipeline execution finished")
    result.modified_files = get_modified_files(workspace_dir)

    return [TextContent(type="text", text=_format_pipeline_result(result, workspace_dir))]


def _format_pipeline_result(result: PipelineResult, workspace_dir: Path) -> str:
    """Format the pipeline result into structured markdown output."""
    output = OutputBuilder()

    output.header("AGENT² PIPELINE EXECUTION COMPLETE", level=1)
    output.blank()
    output.add("**IMPORTANT: The cursor-agent CLI has already executed and made code changes.**")
    output.add("**DO NOT re-implement the changes - they are already saved to disk.**")
    output.blank()

    output.header("Execution Summary")
    output.bullet(f"**Workspace**: `{workspace_dir}`")
    output.bullet(f"**Agents executed**: {', '.join(result.agents_used)}")
    output.bullet(f"**Category**: {result.detected_category}")
    output.blank()

    if result.modified_files:
        output.header("Files Modified")
        for f in result.modified_files[:CONFIG.max_modified_files_shown]:
            output.bullet(f"`{f}`")
        if len(result.modified_files) > CONFIG.max_modified_files_shown:
            output.bullet(f"... and {len(result.modified_files) - CONFIG.max_modified_files_shown} more")
        output.blank()

    output.header("Agent Execution Details")
    for agent_data in result.agent_outputs:
        output.header(agent_data["agent"], level=3)
        if agent_data["focus"]:
            output.field("Focus", agent_data["focus"])
        output.add(truncate_output(agent_data["output"], CONFIG.max_output_length))
        output.blank()

    if result.composer_output:
        output.header("Composer (Integration Validation)", level=3)
        output.add(truncate_output(result.composer_output, CONFIG.max_composer_output_length))
        output.blank()

    output.separator()
    output.header("✅ WORK COMPLETED")
    output.add("The requested changes have been implemented and saved.")
    output.add("**⚠️ NO FURTHER IMPLEMENTATION NEEDED**")

    return output.build()


@register_tool(ToolName.SPLIT_TASK)
async def run_split_task(args: dict[str, Any]) -> list[TextContent]:
    """Run the splitter agent to analyze a task."""
    ac = ensure_agent_chain_imported()
    prompt = args.get("prompt", "")
    workspace_dir = get_workspace(args, WORKSPACE_DIR)

    result, error = await run_with_timeout(ac.split_task, prompt, workspace_dir, timeout_msg="Task splitting")
    if error:
        return [TextContent(type="text", text=error)]

    output = OutputBuilder()
    output.header("Step 1 Complete: Task Analysis")
    output.blank()
    output.field("Requires multiple agents", str(result.get("requires_multiple_agents", False)))
    output.field("Agents needed", ", ".join(result.get("agents_needed", [])))
    output.field("Execution strategy", result.get("execution_strategy", "sequential"))
    output.field("Summary", result.get("summary", "N/A"))
    output.blank()
    output.separator()
    output.add("**Next step**: Call `perfect_prompt` with the same prompt.")

    return [TextContent(type="text", text=output.build())]


@register_tool(ToolName.PERFECT_PROMPT)
async def run_perfect_prompt(args: dict[str, Any]) -> list[TextContent]:
    """Run the prompt engineer to optimize a prompt."""
    ac = ensure_agent_chain_imported()
    prompt = args.get("prompt", "")
    workspace_dir = get_workspace(args, WORKSPACE_DIR)

    result, error = await run_with_timeout(ac.perfect_prompt, prompt, workspace_dir, timeout_msg="Prompt engineering")
    if error:
        return [TextContent(type="text", text=error)]

    perfected, category = result
    output = OutputBuilder()
    output.header("Step 2 Complete: Prompt Optimization")
    output.blank()
    output.field("Category detected", category)
    output.blank()
    output.add("**Optimized prompt**:")
    output.add(perfected)
    output.blank()
    output.separator()
    output.add(f"**Next step**: Call `run_specialist` with agent='{category}'")

    return [TextContent(type="text", text=output.build())]


@register_tool(ToolName.RUN_SPECIALIST)
async def run_specialist(args: dict[str, Any]) -> list[TextContent]:
    """Run a specific specialist agent."""
    ac = ensure_agent_chain_imported()
    agent = args.get("agent", "")
    prompt = args.get("prompt", "")
    workspace_dir = get_workspace(args, WORKSPACE_DIR)

    if not agent:
        return [TextContent(type="text", text="❌ **Error**: Agent name is required.")]

    output = OutputBuilder()
    output.header(f"Running Specialist Agent: {agent}")
    output.field("Workspace", f"`{workspace_dir}`")
    output.blank()

    agent_output = await asyncio.to_thread(ac.execute_agent, agent, prompt, "", False, workspace_dir)
    output.add(agent_output)
    output.blank()
    output.separator()
    output.add(f"**Agent `{agent}` complete.** Changes saved to disk.")

    return [TextContent(type="text", text=output.build())]


@register_tool(ToolName.COMPOSE_AGENTS)
async def run_compose_agents(args: dict[str, Any]) -> list[TextContent]:
    """Run the composer agent to validate integration."""
    ac = ensure_agent_chain_imported()
    agents_used = args.get("agents_used", [])
    prompt = args.get("prompt", "")
    workspace_dir = get_workspace(args, WORKSPACE_DIR)

    if not agents_used or len(agents_used) < 2:
        return [TextContent(type="text", text="⚠️ **Skipping**: Only needed for multiple agents.")]

    output = OutputBuilder()
    output.header("Running Integration Validation (Composer)")
    output.field("Agents", ", ".join(agents_used))
    output.blank()

    composer_output = await asyncio.to_thread(ac.compose_integration, agents_used, prompt, False, workspace_dir)
    output.add(composer_output)
    output.blank()
    output.separator()
    output.header("✅ PIPELINE COMPLETE")
    output.add("All agents have run and integration validated.")
    output.add("**⚠️ NO FURTHER IMPLEMENTATION NEEDED**")

    return [TextContent(type="text", text=output.build())]
