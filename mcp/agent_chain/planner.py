"""
Plan creation module for Agent² system.

This module provides functionality for creating plan documents
that outline the implementation approach before execution.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

from agent_chain.agents import PROMPT_ENGINEER_AGENT
from agent_chain.core import run_cursor_agent, load_agent_instructions, agent_print


def create_plan(
    prompt: str,
    workspace_dir: Path | None = None,
    agent_name: str | None = None,
    focus: str | None = None,
) -> Path | None:
    """
    Create a plan document for the given prompt using prompt engineer agent.

    Args:
        prompt: The task prompt.
        workspace_dir: Workspace directory.
        agent_name: Optional agent name (for multi-agent plans).
        focus: Optional focus area for this agent.

    Returns:
        Path to the created plan file, or None if creation failed.
    """
    if agent_name:
        agent_print(f"📋 Creating plan for {agent_name} agent...")
    else:
        agent_print("📋 Creating plan document...")

    # Load prompt engineer instructions
    prompt_engineer_instructions = load_agent_instructions(
        PROMPT_ENGINEER_AGENT["file"], workspace_dir
    )

    # Build plan prompt with focus if provided
    plan_prompt = _build_plan_prompt(prompt, agent_name, focus)

    output = run_cursor_agent(
        plan_prompt,
        agent_context=prompt_engineer_instructions,
        model=PROMPT_ENGINEER_AGENT["model"],
        output_format="text",
        workspace_dir=workspace_dir,
    )

    if not output.strip():
        agent_print("⚠️  Failed to generate plan content.")
        return None

    # Determine plans directory
    plans_dir = _get_plans_directory(workspace_dir)
    plans_dir.mkdir(parents=True, exist_ok=True)

    # Generate plan file
    plan_path = _generate_plan_file(plans_dir, prompt, agent_name, focus, output)

    if plan_path:
        agent_print(f"✅ Plan created: {plan_path}")

    return plan_path


def _build_plan_prompt(prompt: str, agent_name: str | None, focus: str | None) -> str:
    """Build the prompt for plan generation."""
    if focus and agent_name:
        return f"""You are a prompt engineer. Create a comprehensive plan document for this specific agent task:

Task: "{prompt}"

Agent: {agent_name}
Focus: {focus}

The plan should include:
1. Architecture/Design overview specific to this agent's domain
2. Technology choices and rationale
3. Core components/modules to build
4. Step-by-step implementation approach
5. Dependencies and prerequisites
6. Testing strategy
7. Integration points with other components (if applicable)

Format the plan as a structured markdown document with clear sections.
Be detailed and specific about what this agent needs to build."""
    else:
        return f"""You are a prompt engineer. Create a comprehensive plan document for this task:

"{prompt}"

The plan should include:
1. Architecture overview (if applicable)
2. Tech stack and technology choices
3. Core components/modules
4. Implementation steps in logical order
5. Dependencies and prerequisites
6. Testing strategy
7. Deployment considerations (if applicable)

Format the plan as a structured markdown document with clear sections and subsections.
Be detailed and specific about what needs to be built."""


def _get_plans_directory(workspace_dir: Path | None) -> Path:
    """Get the plans directory path."""
    # Plans dir is at project root (parent of mcp/)
    script_dir = Path(__file__).parent.parent.resolve()
    project_root = script_dir.parent  # Go up from mcp/ to agent-squared/

    if workspace_dir and (workspace_dir / "plans").exists():
        return workspace_dir / "plans"
    else:
        return project_root / "plans"


def _generate_plan_file(
    plans_dir: Path,
    prompt: str,
    agent_name: str | None,
    focus: str | None,
    output: str,
) -> Path | None:
    """Generate and save the plan file."""
    # Generate plan filename
    if agent_name:
        plan_name = re.sub(r"[^a-zA-Z0-9\s-]", "", agent_name)[:30].strip().replace(" ", "-").lower()
        if not plan_name:
            plan_name = "agent"
    else:
        plan_name = re.sub(r"[^a-zA-Z0-9\s-]", "", prompt)[:50].strip().replace(" ", "-").lower()
        if not plan_name:
            plan_name = "plan"

    # Generate UUIDs for plan file (matching Cursor's format)
    plan_id = str(uuid.uuid4()).replace("-", "")
    plan_filename = f"{plan_name}-{plan_id[:8]}.plan.md"
    plan_path = plans_dir / plan_filename

    # Create plan content
    plan_content = _format_plan_content(prompt, agent_name, focus, output, plan_id)

    try:
        plan_path.write_text(plan_content, encoding="utf-8")
        return plan_path
    except Exception as e:
        agent_print(f"⚠️  Failed to save plan: {e}")
        return None


def _format_plan_content(
    prompt: str,
    agent_name: str | None,
    focus: str | None,
    output: str,
    plan_id: str,
) -> str:
    """Format the plan content with metadata."""
    plan_uuid1 = str(uuid.uuid4())
    plan_uuid2 = str(uuid.uuid4())
    plan_title = f"{agent_name}: {prompt}" if agent_name else prompt

    focus_section = f"\n## Focus: {focus}" if focus else ""
    agent_section = f"\n*Agent: {agent_name}*" if agent_name else ""

    return f"""<!-- {plan_uuid1} {plan_uuid2} -->
# {plan_title}
{focus_section}

{output}

---
*Plan created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*Plan ID: {plan_id[:8]}*{agent_section}
"""
