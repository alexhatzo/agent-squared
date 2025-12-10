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

# Lazy imports - only import when needed to avoid startup delays
_agent_chain_imported = False
_agents_cache = None
_additional_agents_cache = None

def _ensure_agent_chain_imported():
    """Lazy import of agent_chain module to avoid startup delays."""
    global _agent_chain_imported, _agents_cache, _additional_agents_cache
    if not _agent_chain_imported:
        try:
            from agent_chain import (
                split_task,
                perfect_prompt,
                execute_agent,
                compose_integration,
                generate_clarification_questions,
                has_enough_info,
                load_agent_instructions,
                run_cursor_agent_detailed,
                set_mcp_mode,
                AGENTS,
                ADDITIONAL_AGENTS,
                SPLITTER_AGENT,
                PROMPT_ENGINEER_AGENT,
                COMPOSER_AGENT,
            )
            
            # Enable MCP mode to redirect all prints to stderr
            # This prevents corrupting the MCP JSON-RPC protocol on stdout
            set_mcp_mode(True)
            
            # Store in module namespace for other functions
            globals().update({
                'split_task': split_task,
                'perfect_prompt': perfect_prompt,
                'execute_agent': execute_agent,
                'compose_integration': compose_integration,
                'generate_clarification_questions': generate_clarification_questions,
                'has_enough_info': has_enough_info,
                'load_agent_instructions': load_agent_instructions,
                'run_cursor_agent_detailed': run_cursor_agent_detailed,
                'AGENTS': AGENTS,
                'ADDITIONAL_AGENTS': ADDITIONAL_AGENTS,
                'SPLITTER_AGENT': SPLITTER_AGENT,
                'PROMPT_ENGINEER_AGENT': PROMPT_ENGINEER_AGENT,
                'COMPOSER_AGENT': COMPOSER_AGENT,
            })
            _agents_cache = list(AGENTS.keys())
            _additional_agents_cache = list(ADDITIONAL_AGENTS.keys())
            _agent_chain_imported = True
        except Exception as e:
            # If import fails, raise a clear error
            _agent_chain_imported = True  # Mark as imported to avoid retry loops
            error_msg = f"Failed to import agent_chain module: {e}\n\nMake sure agent_chain.py is in the same directory as mcp_server.py."
            print(f"Error: {error_msg}", file=sys.stderr)
            raise ImportError(error_msg) from e

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
    # Ensure agent_chain is imported (lazy import to avoid startup delays)
    try:
        _ensure_agent_chain_imported()
    except ImportError as e:
        # If import fails, return a minimal tool list with an error tool
        return [
            Tool(
                name="import_error",
                description=f"MCP Server Error: Failed to import agent_chain module. {str(e)}",
                inputSchema={"type": "object", "properties": {}}
            )
        ]
    
    # Get agent list dynamically
    agent_list = _agents_cache + _additional_agents_cache + ["composer"]
    
    return [
        # ============================================================
        # RECOMMENDED WORKFLOW: Use these tools in sequence for visibility
        # Step 1: split_task -> Step 2: perfect_prompt -> Step 3: run_specialist (for each agent) -> Step 4: compose_agents (if multiple)
        # ============================================================
        Tool(
            name="split_task",
            description="""STEP 1 of Agent² Pipeline: Analyze a task and determine which specialist agents are needed.

RECOMMENDED WORKFLOW for complex tasks:
1. Call split_task first to analyze what agents are needed
2. Show the user the analysis results
3. Call perfect_prompt to optimize the prompt
4. Show the user the optimized prompt
5. Call run_specialist for EACH agent identified (one at a time)
6. Show the user each agent's results
7. If multiple agents were used, call compose_agents to validate integration

This step-by-step approach gives users visibility into each phase.
IMPORTANT: Always pass workspace_dir when the user tags a project folder.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The task to analyze"
                    },
                    "workspace_dir": {
                        "type": "string",
                        "description": "REQUIRED: Path to the project workspace (pass the folder the user tagged)"
                    }
                },
                "required": ["prompt", "workspace_dir"]
            }
        ),
        Tool(
            name="perfect_prompt",
            description="""STEP 2 of Agent² Pipeline: Optimize and improve a prompt using prompt engineering techniques.

Call this AFTER split_task to refine the prompt before running specialist agents.
Returns an optimized prompt and detected category (frontend/backend/cloud/full-stack).
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to optimize"
                    },
                    "workspace_dir": {
                        "type": "string",
                        "description": "REQUIRED: Path to the project workspace"
                    }
                },
                "required": ["prompt", "workspace_dir"]
            }
        ),
        Tool(
            name="run_specialist",
            description="""STEP 3 of Agent² Pipeline: Run a specific specialist agent to implement code changes.

Call this AFTER perfect_prompt, once for EACH agent identified by split_task.
The agent will analyze the codebase and make actual code changes.

Available agents: frontend, backend, cloud, full-stack, code-reviewer, python-pro, ui-ux-designer, security-engineer, ai-engineer, data-engineer, deployment-engineer

IMPORTANT: 
- Always pass workspace_dir
- Call this separately for each agent (not all at once)
- Show results to user between each agent call
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "string",
                        "enum": agent_list,
                        "description": "The specialist agent to run"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The optimized prompt from perfect_prompt"
                    },
                    "workspace_dir": {
                        "type": "string",
                        "description": "REQUIRED: Path to the project workspace (pass the folder the user tagged)"
                    }
                },
                "required": ["agent", "prompt", "workspace_dir"]
            }
        ),
        Tool(
            name="compose_agents",
            description="""STEP 4 of Agent² Pipeline: Validate integration between multiple specialist agents.

Call this AFTER running multiple specialists (e.g., backend + frontend) to ensure their code integrates properly.
The composer will review the changes and fix any integration issues.

Only needed when split_task identified multiple agents.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "agents_used": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of agent names that were run (e.g., ['backend', 'frontend'])"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The original task prompt"
                    },
                    "workspace_dir": {
                        "type": "string",
                        "description": "REQUIRED: Path to the project workspace"
                    }
                },
                "required": ["agents_used", "prompt", "workspace_dir"]
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
        # ============================================================
        # ALTERNATIVE: All-in-one tool (runs everything internally, less visibility)
        # ============================================================
        Tool(
            name="agent_chain",
            description="""[ALTERNATIVE] Run the entire Agent² pipeline in one call.

NOTE: For better visibility, prefer the step-by-step approach:
split_task -> perfect_prompt -> run_specialist (each) -> compose_agents

This tool runs everything internally without intermediate visibility.
Use only when you want quick execution without seeing intermediate steps.

IMPORTANT: Always pass workspace_dir when the user tags a project folder.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The task or question to process through the agent chain"
                    },
                    "workspace_dir": {
                        "type": "string",
                        "description": "REQUIRED: Path to the project workspace (pass the folder the user tagged, e.g. '/Users/name/project')"
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
                "required": ["prompt", "workspace_dir"]
            }
        ),
        # ============================================================
        # UTILITY TOOLS
        # ============================================================
        Tool(
            name="get_clarifying_questions",
            description="""Analyze a task and generate clarifying questions before execution.
            
Use this BEFORE starting the pipeline when you want to gather more information from the user.
Returns questions that should be answered to improve task execution.

Workflow:
1. Call get_clarifying_questions with the initial prompt
2. Ask the user the returned questions
3. Start the pipeline with the enriched prompt including their answers
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
- Proceed with the pipeline (if ready)
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
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    _ensure_agent_chain_imported()
    
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
    elif name == "compose_agents":
        return await run_compose_agents(arguments)
    elif name == "get_clarifying_questions":
        return await run_get_clarifying_questions(arguments)
    elif name == "check_task_readiness":
        return await run_check_task_readiness(arguments)
    elif name == "test_cursor_cli":
        return await run_test_cursor_cli()
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run_agent_chain(args: dict) -> list[TextContent]:
    """Run the full agent chain pipeline with progress updates and clear completion signal."""
    import subprocess
    
    prompt = args.get("prompt", "")
    workspace_dir_str = args.get("workspace_dir", "")
    skip_splitter = args.get("skip_splitter", False)
    skip_prompt_engineering = args.get("skip_prompt_engineering", False)
    category = args.get("category", "auto")
    
    # Use provided workspace or fall back to MCP server directory
    if workspace_dir_str:
        workspace_dir = Path(workspace_dir_str).resolve()
        if not workspace_dir.exists():
            return [TextContent(
                type="text",
                text=f"❌ **Error**: Workspace directory does not exist: {workspace_dir}"
            )]
    else:
        workspace_dir = WORKSPACE_DIR
    
    # Track execution progress and results
    progress_log = []
    agents_used = []
    agent_outputs = []
    
    def log_progress(phase: str, message: str):
        """Log progress to stderr for MCP visibility."""
        progress_log.append(f"[{phase}] {message}")
        # Write to stderr so it shows up in MCP logs
        print(f"🔄 Agent² Progress: [{phase}] {message}", file=sys.stderr)
    
    log_progress("START", f"Pipeline started for workspace: {workspace_dir}")
    log_progress("START", f"Prompt: {prompt[:100]}...")
    
    # Phase 0: Splitter
    splitter_result = None
    if not skip_splitter and category == "auto":
        log_progress("PHASE 0", "Running task decomposition (Splitter Agent)...")
        splitter_result = await asyncio.to_thread(split_task, prompt, workspace_dir)
        agents_needed = splitter_result.get('agents_needed', [])
        log_progress("PHASE 0", f"Complete - Agents needed: {', '.join(agents_needed)}")
    
    # Phase 1: Prompt Engineering
    perfected = prompt
    detected_category = category if category != "auto" else "other"
    
    if not skip_prompt_engineering:
        log_progress("PHASE 1", "Running prompt optimization (Prompt Engineer Agent)...")
        perfected, detected_category = await asyncio.to_thread(perfect_prompt, prompt, workspace_dir)
        log_progress("PHASE 1", f"Complete - Category: {detected_category}")
    
    # Phase 2: Specialist Execution
    log_progress("PHASE 2", "Starting specialist agent execution...")
    
    if splitter_result and splitter_result.get("requires_multiple_agents"):
        for i, agent_plan in enumerate(splitter_result.get("execution_order", []), 1):
            agent_name = agent_plan.get("agent", "")
            agent_focus = agent_plan.get("focus", "")
            agents_used.append(agent_name)
            
            log_progress("PHASE 2", f"Running agent {i}/{len(splitter_result.get('execution_order', []))}: {agent_name}...")
            
            output = await asyncio.to_thread(
                execute_agent, agent_name, perfected, agent_focus, False, workspace_dir
            )
            agent_outputs.append({"agent": agent_name, "focus": agent_focus, "output": output})
            
            log_progress("PHASE 2", f"Agent {agent_name} complete")
    else:
        # Single agent execution
        agents_used.append(detected_category)
        log_progress("PHASE 2", f"Running single agent: {detected_category}...")
        
        output = await asyncio.to_thread(
            execute_agent, detected_category, perfected, "", False, workspace_dir
        )
        agent_outputs.append({"agent": detected_category, "focus": "", "output": output})
        
        log_progress("PHASE 2", f"Agent {detected_category} complete")
    
    # Phase 3: Composer (only when multiple agents were used)
    composer_output = None
    if len(agents_used) > 1:
        log_progress("PHASE 3", "Running integration validation (Composer Agent)...")
        
        composer_output = await asyncio.to_thread(
            compose_integration, agents_used, perfected, False, workspace_dir
        )
        
        log_progress("PHASE 3", "Integration validation complete")
    
    log_progress("DONE", "Pipeline execution finished")
    
    # Try to detect modified files using git
    modified_files = []
    try:
        git_result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(workspace_dir),
            capture_output=True,
            text=True,
            timeout=10
        )
        if git_result.returncode == 0 and git_result.stdout.strip():
            modified_files = [f.strip() for f in git_result.stdout.strip().split('\n') if f.strip()]
    except Exception:
        pass  # Git not available or not a git repo
    
    # Build the final output with clear completion signal
    results = []
    
    # Header
    results.append("# AGENT² PIPELINE EXECUTION COMPLETE")
    results.append("")
    results.append("**IMPORTANT: The cursor-agent CLI has already executed and made code changes.**")
    results.append("**DO NOT re-implement the changes - they are already saved to disk.**")
    results.append("")
    
    # Summary
    results.append("## Execution Summary")
    results.append(f"- **Workspace**: `{workspace_dir}`")
    results.append(f"- **Agents executed**: {', '.join(agents_used)}")
    results.append(f"- **Category**: {detected_category}")
    results.append("")
    
    # Files modified
    if modified_files:
        results.append("## Files Modified")
        results.append("The following files were changed by the agent(s):")
        results.append("")
        for f in modified_files[:20]:  # Limit to first 20
            results.append(f"- `{f}`")
        if len(modified_files) > 20:
            results.append(f"- ... and {len(modified_files) - 20} more files")
        results.append("")
    
    # Agent outputs (condensed)
    results.append("## Agent Execution Details")
    results.append("")
    
    for agent_data in agent_outputs:
        results.append(f"### {agent_data['agent']}")
        if agent_data['focus']:
            results.append(f"**Focus**: {agent_data['focus']}")
        # Truncate long outputs
        output = agent_data['output']
        if len(output) > 2000:
            output = output[:2000] + "\n\n... (output truncated, see files for full changes)"
        results.append(output)
        results.append("")
    
    if composer_output:
        results.append("### Composer (Integration Validation)")
        if len(composer_output) > 1500:
            composer_output = composer_output[:1500] + "\n\n... (output truncated)"
        results.append(composer_output)
        results.append("")
    
    # Clear completion marker
    results.append("---")
    results.append("")
    results.append("## ✅ WORK COMPLETED")
    results.append("")
    results.append("The requested changes have been implemented by the specialist agent(s).")
    results.append("The code modifications are **already saved to the files listed above**.")
    results.append("")
    results.append("### Recommended Next Steps:")
    results.append("1. **Review the modified files** to verify the changes meet requirements")
    results.append("2. **Test the new functionality** to ensure it works correctly")
    results.append("3. **Run linters/tests** if available in the project")
    results.append("")
    results.append("**⚠️ NO FURTHER IMPLEMENTATION NEEDED** - the work is done.")
    
    return [TextContent(type="text", text="\n".join(results))]


def _get_workspace(args: dict) -> Path:
    """Get workspace directory from args or fall back to default."""
    workspace_dir_str = args.get("workspace_dir", "")
    if workspace_dir_str:
        return Path(workspace_dir_str).resolve()
    return WORKSPACE_DIR


async def run_split_task(args: dict) -> list[TextContent]:
    """Run just the splitter agent."""
    prompt = args.get("prompt", "")
    workspace_dir = _get_workspace(args)
    
    result, error = await run_with_timeout_and_errors(
        split_task, prompt, workspace_dir,
        timeout_msg="Task splitting"
    )
    
    if error:
        return [TextContent(type="text", text=error)]
    
    # Format output with clear next steps
    output = []
    output.append("## Step 1 Complete: Task Analysis")
    output.append("")
    output.append(f"**Requires multiple agents**: {result.get('requires_multiple_agents', False)}")
    output.append(f"**Agents needed**: {', '.join(result.get('agents_needed', []))}")
    output.append(f"**Execution strategy**: {result.get('execution_strategy', 'sequential')}")
    output.append(f"**Summary**: {result.get('summary', 'N/A')}")
    output.append("")
    
    if result.get('execution_order'):
        output.append("**Execution order**:")
        for i, step in enumerate(result.get('execution_order', []), 1):
            output.append(f"  {i}. **{step.get('agent', 'unknown')}** - {step.get('focus', 'N/A')}")
        output.append("")
    
    output.append("---")
    output.append("**Next step**: Call `perfect_prompt` with the same prompt to optimize it.")
    
    return [TextContent(type="text", text="\n".join(output))]


async def run_perfect_prompt(args: dict) -> list[TextContent]:
    """Run just the prompt engineer."""
    prompt = args.get("prompt", "")
    workspace_dir = _get_workspace(args)
    
    result, error = await run_with_timeout_and_errors(
        perfect_prompt, prompt, workspace_dir,
        timeout_msg="Prompt engineering"
    )
    
    if error:
        return [TextContent(type="text", text=error)]
    
    perfected, category = result
    
    output = []
    output.append("## Step 2 Complete: Prompt Optimization")
    output.append("")
    output.append(f"**Category detected**: {category}")
    output.append("")
    output.append("**Optimized prompt**:")
    output.append(perfected)
    output.append("")
    output.append("---")
    output.append(f"**Next step**: Call `run_specialist` with agent='{category}' (or each agent from split_task) and this optimized prompt.")
    
    return [TextContent(type="text", text="\n".join(output))]


async def run_list_agents() -> list[TextContent]:
    """List all available agents."""
    _ensure_agent_chain_imported()
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
    _ensure_agent_chain_imported()
    agent = args.get("agent", "")
    prompt = args.get("prompt", "")
    workspace_dir = _get_workspace(args)
    
    results = []
    results.append(f"## Running Specialist Agent: {agent}")
    results.append(f"**Workspace**: `{workspace_dir}`")
    results.append("")
    
    output = await asyncio.to_thread(execute_agent, agent, prompt, "", False, workspace_dir)
    results.append(output)
    results.append("")
    results.append("---")
    results.append(f"**Agent `{agent}` execution complete.** Code changes have been saved to disk.")
    results.append("")
    results.append("Next steps:")
    results.append("- Review the changes above")
    results.append("- If more agents are needed, call `run_specialist` for the next agent")
    results.append("- If multiple agents were used, call `compose_agents` to validate integration")
    
    return [TextContent(type="text", text="\n".join(results))]


async def run_compose_agents(args: dict) -> list[TextContent]:
    """Run the composer agent to validate integration between multiple specialists."""
    _ensure_agent_chain_imported()
    agents_used = args.get("agents_used", [])
    prompt = args.get("prompt", "")
    workspace_dir = _get_workspace(args)
    
    if not agents_used or len(agents_used) < 2:
        return [TextContent(
            type="text",
            text="⚠️ **Skipping composition**: Only needed when multiple agents were used.\n\n"
                 "If you used a single agent, the work is already complete."
        )]
    
    results = []
    results.append(f"## Running Integration Validation (Composer)")
    results.append(f"**Agents to integrate**: {', '.join(agents_used)}")
    results.append(f"**Workspace**: `{workspace_dir}`")
    results.append("")
    
    output = await asyncio.to_thread(compose_integration, agents_used, prompt, False, workspace_dir)
    results.append(output)
    results.append("")
    results.append("---")
    results.append("## ✅ PIPELINE COMPLETE")
    results.append("")
    results.append("All specialist agents have run and integration has been validated.")
    results.append("The code changes are **saved to disk**.")
    results.append("")
    results.append("**⚠️ NO FURTHER IMPLEMENTATION NEEDED** - the work is done.")
    results.append("")
    results.append("Recommended next steps:")
    results.append("1. Review the modified files")
    results.append("2. Test the new functionality")
    results.append("3. Run linters/tests if available")
    
    return [TextContent(type="text", text="\n".join(results))]


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
    """Test if Cursor CLI is working and API key is configured."""
    import subprocess
    import shutil
    
    results = ["## Cursor CLI Diagnostic\n"]
    
    # Check for CURSOR_API_KEY environment variable
    api_key = os.environ.get("CURSOR_API_KEY")
    if api_key:
        # Mask the key for display
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "****"
        results.append(f"✅ CURSOR_API_KEY is set: `{masked_key}`\n")
    else:
        results.append("❌ CURSOR_API_KEY environment variable not set\n")
        results.append("\n**To fix this:**\n")
        results.append("1. Generate an API key from Cursor Settings\n")
        results.append("2. Add it to your MCP config in `~/.cursor/mcp.json`:\n")
        results.append("```json\n")
        results.append('{\n')
        results.append('  "mcpServers": {\n')
        results.append('    "agent-squared": {\n')
        results.append('      "command": "python",\n')
        results.append('      "args": ["/path/to/mcp/mcp_server.py"],\n')
        results.append('      "env": {\n')
        results.append('        "CURSOR_API_KEY": "your-api-key-here"\n')
        results.append('      }\n')
        results.append('    }\n')
        results.append('  }\n')
        results.append('}\n')
        results.append("```\n")
        results.append("3. Restart Cursor to reload the MCP server\n")
        return [TextContent(type="text", text="\n".join(results))]
    
    # Check if cursor-agent command exists (this is the CLI agent, different from cursor IDE)
    cursor_agent_path = shutil.which("cursor-agent")
    
    # Also check common installation locations if not in PATH
    common_paths = [
        os.path.expanduser("~/.local/bin/cursor-agent"),
        os.path.expanduser("~/.cursor/bin/cursor-agent"),
        "/usr/local/bin/cursor-agent",
    ]
    
    if not cursor_agent_path:
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                cursor_agent_path = path
                break
    
    if cursor_agent_path:
        results.append(f"✅ cursor-agent found: `{cursor_agent_path}`\n")
    else:
        results.append("❌ cursor-agent not found in PATH or common locations\n")
        results.append("**To fix:**\n")
        results.append("1. Install Cursor CLI: `curl https://cursor.com/install -fsS | bash`\n")
        results.append("2. Make sure `cursor-agent` is in your PATH\n")
        results.append(f"3. Checked locations: PATH, {', '.join(common_paths)}\n")
        return [TextContent(type="text", text="\n".join(results))]
    
    # Test cursor-agent version
    try:
        version_result = subprocess.run(
            [cursor_agent_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if version_result.returncode == 0:
            results.append(f"✅ Version: `{version_result.stdout.strip()}`\n")
        else:
            results.append(f"⚠️ Version check returned code {version_result.returncode}\n")
            if version_result.stderr:
                results.append(f"   stderr: {version_result.stderr[:200]}\n")
            if version_result.stdout:
                results.append(f"   stdout: {version_result.stdout[:200]}\n")
    except subprocess.TimeoutExpired:
        results.append("⚠️ Version check timed out\n")
    except Exception as e:
        results.append(f"⚠️ Version check error: {e}\n")
    
    # Test a simple agent call with timeout
    results.append("\n### Testing Agent Call (30s timeout)...\n")
    
    # Use discovered cursor_agent_path instead of relying on PATH
    # Pass API key explicitly via flag (in addition to env var)
    test_cmd = [cursor_agent_path]
    if api_key:
        test_cmd.extend(["--api-key", api_key])
    test_cmd.extend(["-p", "Say hello", "--output-format", "text", "--force"])
    
    # Show command with masked API key for display
    display_cmd = [cursor_agent_path]
    if api_key:
        display_cmd.extend(["--api-key", "***"])
    display_cmd.extend(["-p", "Say hello", "--output-format", "text", "--force"])
    results.append(f"**Command:** `{' '.join(display_cmd)}`\n")
    results.append(f"**Working dir:** `{WORKSPACE_DIR}`\n")
    
    # Show relevant environment variables
    results.append("\n**Environment:**\n")
    results.append(f"- CURSOR_API_KEY: {'set' if api_key else 'NOT SET'}\n")
    results.append(f"- HOME: {os.environ.get('HOME', 'not set')}\n")
    
    # Try with Popen to get real-time info
    try:
        import time
        start_time = time.time()
        
        # Pass full environment to subprocess
        env = os.environ.copy()
        
        # Redirect stdin from /dev/null to prevent interactive prompts
        process = subprocess.Popen(
            test_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(WORKSPACE_DIR),
            env=env
        )
        
        try:
            stdout, stderr = process.communicate(timeout=30)
            elapsed = time.time() - start_time
            
            results.append(f"\n**Completed in:** {elapsed:.1f}s\n")
            results.append(f"**Return code:** {process.returncode}\n")
            
            if process.returncode == 0:
                output_preview = stdout[:500] + "..." if len(stdout) > 500 else stdout
                results.append(f"✅ Agent call succeeded!\n")
                results.append(f"**Response:**\n```\n{output_preview}\n```\n")
            else:
                results.append(f"❌ Agent call failed\n")
                if stdout:
                    results.append(f"**Stdout:**\n```\n{stdout[:500]}\n```\n")
                if stderr:
                    results.append(f"**Stderr:**\n```\n{stderr[:500]}\n```\n")
                    
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            process.kill()
            stdout, stderr = process.communicate()
            
            results.append(f"\n⏱️ **Timeout after {elapsed:.1f}s**\n")
            results.append("\n**Partial output captured:**\n")
            if stdout:
                results.append(f"**Stdout:** `{stdout[:300]}`\n")
            else:
                results.append("**Stdout:** (empty)\n")
            if stderr:
                results.append(f"**Stderr:** `{stderr[:300]}`\n")
            else:
                results.append("**Stderr:** (empty)\n")
            
            results.append("\n**Debug info:**\n")
            results.append(f"- Process PID was: {process.pid}\n")
            results.append("- The process was killed after timeout\n")
            results.append("\n**Possible causes:**\n")
            results.append("1. Keychain access issue (SecItemCopyMatching error)\n")
            results.append("2. Network connectivity from subprocess\n")
            results.append("3. cursor-agent waiting for interactive input\n")
            
    except FileNotFoundError:
        results.append("❌ cursor-agent command not found\n")
    except Exception as e:
        results.append(f"❌ Error: {type(e).__name__}: {e}\n")
    
    return [TextContent(type="text", text="\n".join(results))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

