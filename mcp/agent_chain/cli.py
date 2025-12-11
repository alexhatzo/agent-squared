"""
CLI module for Agent² system.

This module provides the command-line interface for running the agent chain.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_chain.core import agent_print
from agent_chain.splitter import split_task
from agent_chain.prompt_engineer import (
    perfect_prompt,
    generate_clarification_questions,
    has_enough_info,
)
from agent_chain.executor import execute_multiple_agents, execute_with_specialist
from agent_chain.planner import create_plan


def interactive_clarification(initial_prompt: str, workspace_dir: Path | None = None) -> str:
    """
    Interactive clarification loop that asks questions until enough info is gathered.

    This is only used in CLI mode, not in MCP mode.

    Args:
        initial_prompt: The original user prompt.
        workspace_dir: Optional workspace directory.

    Returns:
        Refined prompt with all answers incorporated.
    """
    agent_print("💬 Phase 0.5: Interactive Clarification...")
    agent_print("=" * 80)
    agent_print("The prompt engineer will ask clarifying questions to refine your prompt.")
    agent_print("Answer each question, or type 'build' when ready to proceed.\n")

    accumulated_answers: dict[str, str] = {}
    current_prompt = initial_prompt
    round_number = 0

    try:
        while True:
            round_number += 1

            # Generate questions for this round
            questions, analysis = generate_clarification_questions(
                current_prompt,
                accumulated_answers if accumulated_answers else None,
                workspace_dir,
            )

            # If no questions and we have some answers, check if enough info
            if not questions:
                if accumulated_answers:
                    if has_enough_info(current_prompt, accumulated_answers, workspace_dir):
                        agent_print("✅ Prompt engineer has enough information to proceed.\n")
                        break
                    else:
                        agent_print("⚠️  No more questions, but information may still be incomplete.")
                        agent_print("Type 'build' to proceed anyway, or provide additional context.\n")
                        user_input = input("Your response (or 'build' to proceed): ").strip()
                        if user_input.lower() == "build":
                            agent_print("\n🚀 Proceeding with current information...\n")
                            break
                        elif user_input:
                            accumulated_answers["Additional context"] = user_input
                            current_prompt = _build_refined_prompt(initial_prompt, accumulated_answers)
                            agent_print("✅ Additional context recorded.\n")
                            continue
                        else:
                            agent_print("Proceeding with current information...\n")
                            break
                else:
                    agent_print("✅ No clarification needed. Prompt is clear and complete.\n")
                    break

            # Display questions
            if questions:
                agent_print(f"\n📋 Round {round_number} - Questions:")
                agent_print("-" * 80)
                for i, question in enumerate(questions, 1):
                    agent_print(f"{i}. {question}")
                agent_print("-" * 80)
                if analysis:
                    agent_print(f"\n💡 Analysis: {analysis}\n")
                agent_print("(Type 'build' when ready to proceed, or provide your answers)\n")

            # Get user input
            user_input = input("Your response: ").strip()

            if user_input.lower() == "build":
                agent_print("\n🚀 Proceeding with current information...\n")
                break

            if user_input:
                for question in questions:
                    accumulated_answers[question] = user_input
                current_prompt = _build_refined_prompt(initial_prompt, accumulated_answers)
                agent_print(
                    f"✅ Answer recorded. ({len(questions)} question(s) answered, "
                    f"{len(accumulated_answers)} total clarification(s))\n"
                )
            else:
                agent_print("⚠️  Empty input. Please provide an answer or type 'build' to proceed.\n")

        agent_print("=" * 80)
        return _build_refined_prompt(initial_prompt, accumulated_answers) if accumulated_answers else initial_prompt

    except KeyboardInterrupt:
        agent_print("\n\n⚠️  Clarification interrupted by user.")
        agent_print("Proceeding with current information...\n")
        return _build_refined_prompt(initial_prompt, accumulated_answers) if accumulated_answers else initial_prompt


def _build_refined_prompt(initial_prompt: str, accumulated_answers: dict[str, str]) -> str:
    """Build refined prompt with accumulated answers."""
    if not accumulated_answers:
        return initial_prompt

    answers_section = "\n\n### Clarifications:\n"
    for question, answer in accumulated_answers.items():
        answers_section += f"- {question}: {answer}\n"

    return f"{initial_prompt}{answers_section}"


def main() -> None:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Chain Cursor agents: Prompt Engineer → Specialist Agent(s)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Non-interactive mode (prints output to console)
  python agent_chain.py "Build a login page with authentication"
  
  # Interactive mode (opens Cursor UI for each agent)
  python agent_chain.py "Create a REST API for user management" --interactive
  
  # Skip prompt engineering (use original prompt directly)
  python agent_chain.py "Add dark mode to the app" --skip-prompt-engineering
        """,
    )

    parser.add_argument("prompt", help="Initial prompt/request")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run agents in interactive mode (opens Cursor UI instead of printing output)",
    )
    parser.add_argument(
        "--skip-splitter",
        action="store_true",
        help="Skip splitter agent phase (go directly to prompt engineering)",
    )
    parser.add_argument(
        "--skip-prompt-engineering",
        action="store_true",
        help="Skip prompt engineering phase and go directly to specialist agent",
    )
    parser.add_argument(
        "--skip-clarification",
        action="store_true",
        help="Skip the interactive clarification phase (default: clarification enabled)",
    )
    parser.add_argument(
        "--category",
        choices=["frontend", "backend", "cloud", "full-stack", "other"],
        help="Force a specific category (skips categorization)",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        help="Project workspace directory (default: parent of .cursor directory)",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Create a plan document before execution (saved to .cursor/plans/)",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Only create a plan document, do not execute agents",
    )

    args = parser.parse_args()

    # Determine workspace directory
    if args.workspace:
        workspace_dir = Path(args.workspace).resolve()
        if not workspace_dir.exists():
            agent_print(f"Error: Workspace directory does not exist: {workspace_dir}", file=sys.stderr)
            sys.exit(1)
        if not workspace_dir.is_dir():
            agent_print(f"Error: Workspace path is not a directory: {workspace_dir}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default: parent of mcp directory
        workspace_dir = Path(__file__).parent.parent.parent.resolve()

    agent_print(f"📁 Workspace: {workspace_dir}")
    agent_print(f"📁 Agent will have access to codebase in: {workspace_dir}\n")

    agent_print("=" * 80)
    agent_print("CURSOR AGENT CHAIN ORCHESTRATOR")
    agent_print("=" * 80)
    agent_print(f"Initial Prompt: {args.prompt}\n")

    # Plan creation phase (if requested)
    if args.plan or args.plan_only:
        create_plan(args.prompt, workspace_dir=workspace_dir)
        if args.plan_only:
            agent_print("\n" + "=" * 80)
            agent_print("✅ Plan-only mode: Exiting after plan creation")
            agent_print("=" * 80)
            return

    # Phase 0: Splitter agent (unless skipped)
    splitter_result = None
    if not args.skip_splitter and not args.skip_prompt_engineering and not args.category:
        splitter_result = split_task(args.prompt, workspace_dir=workspace_dir)
        agent_print(f"\n✅ Splitter Analysis:")
        agent_print(f"   Requires multiple agents: {splitter_result.get('requires_multiple_agents', False)}")
        agent_print(f"   Agents needed: {', '.join(splitter_result.get('agents_needed', []))}")
        agent_print(f"   Strategy: {splitter_result.get('execution_strategy', 'sequential')}")
        agent_print(f"   Summary: {splitter_result.get('summary', 'N/A')}\n")

    # Phase 0.5: Interactive Clarification (unless skipped)
    clarified_prompt = args.prompt
    if not args.skip_clarification and not args.skip_prompt_engineering and not args.category:
        clarified_prompt = interactive_clarification(args.prompt, workspace_dir=workspace_dir)
        preview = f"{clarified_prompt[:200]}..." if len(clarified_prompt) > 200 else clarified_prompt
        agent_print(f"✅ Clarified Prompt: {preview}\n")
    elif args.skip_clarification:
        agent_print("⏭️  Skipping clarification phase.\n")

    # Phase 1: Prompt engineering (unless skipped)
    if args.skip_prompt_engineering or args.category:
        perfected_prompt = clarified_prompt
        category = args.category or "other"
        agent_print(f"⏭️  Skipping prompt engineering. Using category: {category}")
    else:
        perfected_prompt, category = perfect_prompt(clarified_prompt, workspace_dir=workspace_dir)
        agent_print(f"\n✅ Categorized as: {category}")
        agent_print(f"✅ Perfected Prompt: {perfected_prompt}\n")

    # Phase 2: Execute agents
    create_agent_plans = args.plan or (
        splitter_result and splitter_result.get("requires_multiple_agents", False)
    )

    if splitter_result and splitter_result.get("requires_multiple_agents", False):
        execute_multiple_agents(
            splitter_result,
            perfected_prompt,
            interactive=args.interactive,
            workspace_dir=workspace_dir,
            create_plans=create_agent_plans,
        )
    else:
        if create_agent_plans:
            create_plan(perfected_prompt, workspace_dir=workspace_dir, agent_name=category)
        execute_with_specialist(
            perfected_prompt,
            category,
            interactive=args.interactive,
            workspace_dir=workspace_dir,
        )

    agent_print("\n" + "=" * 80)
    agent_print("✅ Agent chain completed!")
    agent_print("=" * 80)


if __name__ == "__main__":
    main()
