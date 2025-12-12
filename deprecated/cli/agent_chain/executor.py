"""
Agent executor module for Agent² CLI.

This module provides functionality for executing specialist agents
and composing their outputs.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from agent_chain.agents import (
    AGENTS,
    ADDITIONAL_AGENTS,
    COMPOSER_AGENT,
    get_agent_config,
)
from agent_chain.core import (
    run_cursor_agent,
    load_agent_instructions,
    find_cursor_agent,
)
from agent_chain.planner import create_plan


def execute_agent(
    agent_name: str,
    prompt: str,
    focus: str = "",
    interactive: bool = False,
    workspace_dir: Path | None = None,
) -> str:
    """
    Execute a single agent with the given prompt.

    Args:
        agent_name: Name of the agent to execute.
        prompt: The prompt for the agent.
        focus: Optional focus area for the agent (appended to prompt).
        interactive: Run in interactive mode (opens Cursor UI).
        workspace_dir: Workspace directory for codebase context.

    Returns:
        Agent output string (empty string in interactive mode).
    """
    # Build full prompt with focus if provided
    full_prompt = f"{prompt}\n\nFocus: {focus}" if focus else prompt

    # Look up agent configuration
    agent_config = get_agent_config(agent_name)

    if not agent_config:
        print(f"⚠️  Unknown agent: {agent_name}. Using default agent.")
        return _run_default_agent(full_prompt, interactive, workspace_dir)

    # Handle composite agents (like full-stack) that have sub-agents
    if "agents" in agent_config:
        print(f"🔀 Running composite agent: {agent_name}")
        results = []
        for sub_agent_name in agent_config["agents"]:
            result = execute_agent(sub_agent_name, prompt, focus, interactive, workspace_dir)
            results.append(result)
        # Run composer to integrate
        if len(agent_config["agents"]) > 1:
            compose_result = compose_integration(
                agent_config["agents"], prompt, interactive, workspace_dir
            )
            results.append(compose_result)
        return "\n\n".join(results)

    # Load agent instructions (only for non-composite agents)
    agent_instructions = load_agent_instructions(agent_config["file"], workspace_dir)

    if interactive:
        return _run_interactive_agent(agent_config, full_prompt, workspace_dir)
    else:
        return _run_agent_with_output(agent_config, full_prompt, agent_instructions, workspace_dir)


def execute_multiple_agents(
    splitter_result: dict[str, Any],
    perfected_prompt: str,
    interactive: bool = False,
    workspace_dir: Path | None = None,
    create_plans: bool = True,
) -> None:
    """
    Execute multiple agents based on splitter analysis.

    Args:
        splitter_result: Result from splitter agent analysis.
        perfected_prompt: The perfected prompt.
        interactive: Run in interactive mode.
        workspace_dir: Workspace directory.
        create_plans: Whether to create a plan for each agent before execution.
    """
    print(f"\n🚀 Phase 2: Executing with {len(splitter_result.get('execution_order', []))} agent(s)...\n")
    print(f"Strategy: {splitter_result.get('execution_strategy', 'sequential')}\n")

    execution_order = splitter_result.get("execution_order", [])

    if not execution_order:
        print("⚠️  No execution order specified. Using default single agent.")
        execute_with_specialist(perfected_prompt, "other", interactive, workspace_dir)
        return

    # Execute agents in order
    for i, agent_plan in enumerate(execution_order, 1):
        agent_name = agent_plan.get("agent", "")
        agent_focus = agent_plan.get("focus", "")
        agent_reason = agent_plan.get("reason", "")

        print(f"\n{'=' * 80}")
        print(f"Agent {i}/{len(execution_order)}: {agent_name}")
        print(f"Reason: {agent_reason}")
        if agent_focus:
            print(f"Focus: {agent_focus}")
        print(f"{'=' * 80}\n")

        # Create plan for this agent before execution (if requested)
        if create_plans:
            agent_plan_prompt = perfected_prompt
            if agent_focus:
                agent_plan_prompt = f"{perfected_prompt}\n\nFocus: {agent_focus}"

            plan_path = create_plan(
                agent_plan_prompt,
                workspace_dir=workspace_dir,
                agent_name=agent_name,
                focus=agent_focus,
            )
            if plan_path:
                print(f"📄 Plan saved for {agent_name} agent\n")

        # Build prompt for this agent
        agent_prompt = perfected_prompt
        if agent_focus:
            agent_prompt = f"{perfected_prompt}\n\nSpecific focus for this agent: {agent_focus}"

        execute_agent(agent_name, agent_prompt, agent_focus, interactive, workspace_dir)

        # If sequential, wait for this agent to complete before next
        if splitter_result.get("execution_strategy") == "sequential" and i < len(execution_order):
            print("\n⏳ Waiting for agent to complete before proceeding to next...\n")

    # Phase 3: Run composer agent to validate integration (if multiple agents were used)
    if len(execution_order) > 1:
        compose_integration(
            agents_used=[ep.get("agent", "") for ep in execution_order],
            original_prompt=perfected_prompt,
            interactive=interactive,
            workspace_dir=workspace_dir,
        )


def compose_integration(
    agents_used: list[str],
    original_prompt: str,
    interactive: bool = False,
    workspace_dir: Path | None = None,
) -> str:
    """
    Run the composer agent to validate that code from multiple agents integrates properly.

    The composer agent will:
    1. Review changes made by each specialist agent
    2. Verify integration between components
    3. Check API contracts and type consistency
    4. Fix any integration issues

    Args:
        agents_used: List of agent names that were executed.
        original_prompt: The original task prompt.
        interactive: Run in interactive mode (opens Cursor UI).
        workspace_dir: Workspace directory.

    Returns:
        Composer agent output string.
    """
    print("\n" + "=" * 80)
    print("🎼 Phase 3: Running Composer Agent for Integration Validation")
    print("=" * 80)
    print(f"Validating integration between: {', '.join(agents_used)}\n")

    # Load composer agent instructions
    composer_instructions = load_agent_instructions(COMPOSER_AGENT["file"], workspace_dir)

    # Build agent list for prompt
    agents_list = "\n".join(f"- {agent}" for agent in agents_used)

    # Build the composer prompt
    composer_prompt = f"""You are the integration composer. Multiple specialist agents have just completed work on this task:

**Original Task:** {original_prompt}

**Agents that contributed:**
{agents_list}

**Your job:**
1. Review the code/changes made by each agent
2. Verify that their outputs integrate correctly
3. Check API contracts, data flow, type consistency
4. Fix any integration issues you find
5. Add any missing glue code

Start by examining recent changes (git diff or read modified files), then validate integration points between the components.

Output a clear integration report showing what was validated and any fixes made."""

    if interactive:
        print("Opening composer agent in Cursor...")
        try:
            cursor_agent = find_cursor_agent()
            subprocess.run(
                [cursor_agent, "--model", COMPOSER_AGENT["model"], composer_prompt],
                cwd=str(workspace_dir) if workspace_dir else None,
            )
        except FileNotFoundError as e:
            print(f"Error: Cursor agent not found: {e}", file=sys.stderr)
        return ""
    else:
        output = run_cursor_agent(
            composer_prompt,
            agent_context=composer_instructions,
            model=COMPOSER_AGENT["model"],
            workspace_dir=workspace_dir,
        )
        print("\n" + "=" * 80)
        print("COMPOSER AGENT OUTPUT:")
        print("=" * 80)
        print(output)
        print("=" * 80 + "\n")
        return output


def execute_with_specialist(
    prompt: str,
    category: str,
    interactive: bool = False,
    workspace_dir: Path | None = None,
) -> None:
    """
    Execute the task using the appropriate specialist agent(s).

    This is a legacy function for single-agent execution.

    Args:
        prompt: The perfected prompt.
        category: Task category (frontend, backend, cloud, full-stack, other).
        interactive: If True, run in interactive mode (opens Cursor UI).
        workspace_dir: Workspace directory for codebase context.
    """
    print(f"\n🚀 Phase 2: Executing with {category} specialist agent(s)...\n")

    if category == "full-stack":
        _execute_full_stack(prompt, interactive, workspace_dir)
    elif category in AGENTS:
        _execute_single_agent(AGENTS[category], prompt, interactive, workspace_dir)
    else:
        print(f"⚠️  Unknown category '{category}'. Running with default agent...")
        _run_default_agent(prompt, interactive, workspace_dir)


# ==============================================================================
# PRIVATE HELPER FUNCTIONS
# ==============================================================================

def _run_default_agent(prompt: str, interactive: bool, workspace_dir: Path | None) -> str:
    """Run the default agent when no specific agent is found."""
    if interactive:
        try:
            cursor_agent = find_cursor_agent()
            subprocess.run(
                [cursor_agent, prompt],
                cwd=str(workspace_dir) if workspace_dir else None,
            )
        except FileNotFoundError as e:
            print(f"Error: Cursor agent not found: {e}", file=sys.stderr)
        return ""
    else:
        return run_cursor_agent(prompt, workspace_dir=workspace_dir)


def _run_interactive_agent(
    agent_config: dict[str, Any],
    prompt: str,
    workspace_dir: Path | None,
) -> str:
    """Run an agent in interactive mode."""
    print(f"Opening {agent_config['name']} agent in Cursor...")
    try:
        cursor_agent = find_cursor_agent()
        subprocess.run(
            [cursor_agent, "--model", agent_config["model"], prompt],
            cwd=str(workspace_dir) if workspace_dir else None,
        )
    except FileNotFoundError as e:
        print(f"Error: Cursor agent not found: {e}", file=sys.stderr)
    return ""


def _run_agent_with_output(
    agent_config: dict[str, Any],
    prompt: str,
    agent_instructions: str,
    workspace_dir: Path | None,
) -> str:
    """Run an agent and print its output."""
    output = run_cursor_agent(
        prompt,
        agent_context=agent_instructions,
        model=agent_config["model"],
        workspace_dir=workspace_dir,
    )

    agent_display_name = agent_config["name"].upper().replace("-", " ")
    print("\n" + "=" * 80)
    print(f"{agent_display_name} OUTPUT:")
    print("=" * 80)
    print(output)
    print("=" * 80 + "\n")

    return output


def _execute_full_stack(prompt: str, interactive: bool, workspace_dir: Path | None) -> None:
    """Execute a full-stack task (backend first, then frontend)."""
    # Execute backend first
    print("📦 Step 2a: Backend Architecture...")
    backend_agent = AGENTS["backend"]
    backend_instructions = load_agent_instructions(backend_agent["file"], workspace_dir)

    backend_prompt = f"""This is a full-stack task. Focus on the backend/API layer first.

{prompt}

Provide:
- API endpoint definitions
- Database schema
- Service architecture
- Backend implementation details
"""

    if interactive:
        _run_interactive_agent(backend_agent, backend_prompt, workspace_dir)
    else:
        _run_agent_with_output(backend_agent, backend_prompt, backend_instructions, workspace_dir)

    # Execute frontend
    print("\n🎨 Step 2b: Frontend Implementation...")
    frontend_agent = AGENTS["frontend"]
    frontend_instructions = load_agent_instructions(frontend_agent["file"], workspace_dir)

    frontend_prompt = f"""This is a full-stack task. Now focus on the frontend/UI layer.

{prompt}

Provide:
- React components
- Styling implementation
- State management
- Frontend integration with the backend API
"""

    if interactive:
        _run_interactive_agent(frontend_agent, frontend_prompt, workspace_dir)
    else:
        _run_agent_with_output(frontend_agent, frontend_prompt, frontend_instructions, workspace_dir)

    # Run composer to validate integration
    compose_integration(
        agents_used=["backend-architect", "frontend-developer"],
        original_prompt=prompt,
        interactive=interactive,
        workspace_dir=workspace_dir,
    )


def _execute_single_agent(
    agent: dict[str, Any],
    prompt: str,
    interactive: bool,
    workspace_dir: Path | None,
) -> None:
    """Execute a single specialist agent."""
    agent_instructions = load_agent_instructions(agent["file"], workspace_dir)

    if interactive:
        _run_interactive_agent(agent, prompt, workspace_dir)
    else:
        _run_agent_with_output(agent, prompt, agent_instructions, workspace_dir)
