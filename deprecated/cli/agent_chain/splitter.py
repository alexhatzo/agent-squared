"""
Task splitter module for Agent² CLI.

This module provides functionality to analyze prompts and determine
which specialist agents are needed to complete a task.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_chain.agents import SPLITTER_AGENT
from agent_chain.core import run_cursor_agent, load_agent_instructions


@dataclass
class SplitterResult:
    """Result from the splitter agent analysis."""

    requires_multiple_agents: bool = False
    agents_needed: list[str] = field(default_factory=list)
    execution_strategy: str = "sequential"
    execution_order: list[dict[str, str]] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    summary: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SplitterResult":
        """Create a SplitterResult from a dictionary."""
        return cls(
            requires_multiple_agents=data.get("requires_multiple_agents", False),
            agents_needed=data.get("agents_needed", []),
            execution_strategy=data.get("execution_strategy", "sequential"),
            execution_order=data.get("execution_order", []),
            dependencies=data.get("dependencies", {}),
            summary=data.get("summary", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            "requires_multiple_agents": self.requires_multiple_agents,
            "agents_needed": self.agents_needed,
            "execution_strategy": self.execution_strategy,
            "execution_order": self.execution_order,
            "dependencies": self.dependencies,
            "summary": self.summary,
        }


def split_task(initial_prompt: str, workspace_dir: Path | None = None) -> dict[str, Any]:
    """
    Use splitter agent to analyze the prompt and determine which agents are needed.

    Args:
        initial_prompt: The user's task description.
        workspace_dir: Optional workspace directory.

    Returns:
        Dictionary with splitter analysis containing:
        - requires_multiple_agents: bool
        - agents_needed: list of agent names
        - execution_strategy: "sequential" or "parallel"
        - execution_order: list of agent execution plans
        - dependencies: dict of agent dependencies
        - summary: brief explanation
    """
    print("🔀 Phase 0: Analyzing task with Splitter agent...")

    # Load splitter agent instructions
    splitter_instructions = load_agent_instructions(SPLITTER_AGENT["file"], workspace_dir)

    splitter_prompt = f"""Analyze this user prompt and determine which specialized agents are needed:

"{initial_prompt}"

Output your analysis in the required JSON format with:
- requires_multiple_agents (true/false)
- agents_needed (list of agent names)
- execution_strategy ("sequential" or "parallel")
- execution_order (list of agent execution plans)
- dependencies (if any)
- summary (brief explanation)

Make sure to output ONLY valid JSON, no markdown formatting."""

    output = run_cursor_agent(
        splitter_prompt,
        agent_context=splitter_instructions,
        model=SPLITTER_AGENT["model"],
        output_format="text",
        workspace_dir=workspace_dir,
    )

    print("\n" + "=" * 80)
    print("SPLITTER AGENT OUTPUT:")
    print("=" * 80)
    print(output)
    print("=" * 80 + "\n")

    # Try to extract JSON from output
    splitter_result = _parse_json_from_output(output)

    # Fallback: if no JSON found, assume single agent
    if splitter_result is None:
        print("⚠️  Could not parse splitter JSON. Defaulting to single agent workflow.")
        splitter_result = SplitterResult(
            summary="Could not parse splitter output, using default"
        ).to_dict()

    return splitter_result


def _parse_json_from_output(output: str) -> dict[str, Any] | None:
    """
    Extract and parse JSON from agent output.

    Args:
        output: The raw output from an agent.

    Returns:
        Parsed JSON dictionary or None if parsing fails.
    """
    json_match = re.search(r"\{[\s\S]*\}", output)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    return None
