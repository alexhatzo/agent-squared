"""
CLI module for Agent² system.

This module provides the command-line interface for running the agent chain.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_chain.agents import get_all_agent_names
from agent_chain.splitter import split_task
from agent_chain.prompt_engineer import (
    perfect_prompt,
    generate_clarification_questions,
    has_enough_info,
)
from agent_chain.executor import execute_multiple_agents, execute_with_specialist
from agent_chain.planner import create_plan
from agent_chain.core import find_cursor_agent
from agent_chain.config import CLI_DIR, get_model, get_default_workspace, validate_workspace


def interactive_clarification(initial_prompt: str, workspace_dir: Path | None = None) -> str:
    """
    Interactive clarification loop that asks questions until enough info is gathered.

    This is only used in CLI mode for interactive terminal sessions.

    Args:
        initial_prompt: The original user prompt.
        workspace_dir: Optional workspace directory.

    Returns:
        Refined prompt with all answers incorporated.
    """
    print("💬 Phase 0.5: Interactive Clarification...")
    print("=" * 80)
    print("The prompt engineer will ask clarifying questions to refine your prompt.")
    print("Answer each question, or type 'build' when ready to proceed.\n")

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
                        print("✅ Prompt engineer has enough information to proceed.\n")
                        break
                    else:
                        print("⚠️  No more questions, but information may still be incomplete.")
                        print("Type 'build' to proceed anyway, or provide additional context.\n")
                        user_input = input("Your response (or 'build' to proceed): ").strip()
                        if user_input.lower() == "build":
                            print("\n🚀 Proceeding with current information...\n")
                            break
                        elif user_input:
                            accumulated_answers["Additional context"] = user_input
                            current_prompt = _build_refined_prompt(initial_prompt, accumulated_answers)
                            print("✅ Additional context recorded.\n")
                            continue
                        else:
                            print("Proceeding with current information...\n")
                            break
                else:
                    print("✅ No clarification needed. Prompt is clear and complete.\n")
                    break

            # Display questions
            if questions:
                print(f"\n📋 Round {round_number} - Questions:")
                print("-" * 80)
                for i, question in enumerate(questions, 1):
                    print(f"{i}. {question}")
                print("-" * 80)
                if analysis:
                    print(f"\n💡 Analysis: {analysis}\n")
                print("(Type 'build' when ready to proceed, or provide your answers)\n")

            # Get user input
            user_input = input("Your response: ").strip()

            if user_input.lower() == "build":
                print("\n🚀 Proceeding with current information...\n")
                break

            if user_input:
                for question in questions:
                    accumulated_answers[question] = user_input
                current_prompt = _build_refined_prompt(initial_prompt, accumulated_answers)
                print(
                    f"✅ Answer recorded. ({len(questions)} question(s) answered, "
                    f"{len(accumulated_answers)} total clarification(s))\n"
                )
            else:
                print("⚠️  Empty input. Please provide an answer or type 'build' to proceed.\n")

        print("=" * 80)
        return _build_refined_prompt(initial_prompt, accumulated_answers) if accumulated_answers else initial_prompt

    except KeyboardInterrupt:
        print("\n\n⚠️  Clarification interrupted by user.")
        print("Proceeding with current information...\n")
        return _build_refined_prompt(initial_prompt, accumulated_answers) if accumulated_answers else initial_prompt


def _build_refined_prompt(initial_prompt: str, accumulated_answers: dict[str, str]) -> str:
    """Build refined prompt with accumulated answers."""
    if not accumulated_answers:
        return initial_prompt

    answers_section = "\n\n### Clarifications:\n"
    for question, answer in accumulated_answers.items():
        answers_section += f"- {question}: {answer}\n"

    return f"{initial_prompt}{answers_section}"


def test_cursor_cli() -> None:
    """Test if Cursor CLI is working and properly configured."""
    print("=" * 80)
    print("CURSOR CLI DIAGNOSTIC")
    print("=" * 80 + "\n")

    # Check model configuration
    model = get_model()
    print(f"📊 Model: {model} (set via CURSOR_MODEL env var)\n")

    # Check for cursor-agent executable
    try:
        cursor_agent_path = find_cursor_agent()
        print(f"✅ cursor-agent found: {cursor_agent_path}")
    except FileNotFoundError as e:
        print(f"❌ cursor-agent not found: {e}")
        print("\nTo fix:")
        print("  1. Install Cursor CLI: curl https://cursor.com/install -fsS | bash")
        print("  2. Make sure cursor-agent is in your PATH")
        return

    # Check for API key
    import os
    api_key = os.environ.get("CURSOR_API_KEY")
    if api_key:
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"✅ CURSOR_API_KEY is set: {masked_key}")
    else:
        print("⚠️  CURSOR_API_KEY not set (may use default authentication)")

    print("\n" + "=" * 80)
    print("✅ Cursor CLI is configured correctly!")
    print("=" * 80)


def list_agents() -> None:
    """List all available agents."""
    from agent_chain.agents import AGENTS, ADDITIONAL_AGENTS

    print("=" * 80)
    print("AVAILABLE AGENTS")
    print("=" * 80 + "\n")

    print("📦 Core Agents:")
    print("-" * 40)
    for key, agent in AGENTS.items():
        if "agents" not in agent:  # Skip composite agents
            print(f"  • {key} ({agent['name']})")
        else:
            print(f"  • {key} (composite: {', '.join(agent['agents'])})")

    print("\n🔧 Additional Agents:")
    print("-" * 40)
    for key, agent in ADDITIONAL_AGENTS.items():
        print(f"  • {key} ({agent['name']})")

    print("\n" + "=" * 80)


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

  # Test Cursor CLI configuration
  python agent_chain.py --test-cli

  # List available agents
  python agent_chain.py --list-agents

Environment Variables:
  CURSOR_API_KEY    API key for Cursor CLI authentication
  CURSOR_MODEL      Model to use (default: composer-1)
        """,
    )

    parser.add_argument("prompt", nargs="?", help="Initial prompt/request")
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
        help="Project workspace directory (default: current working directory)",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Create a plan document before execution (saved to plans/)",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Only create a plan document, do not execute agents",
    )
    parser.add_argument(
        "--test-cli",
        action="store_true",
        help="Test Cursor CLI configuration and exit",
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List all available agents and exit",
    )

    args = parser.parse_args()

    # Handle utility commands
    if args.test_cli:
        test_cursor_cli()
        return

    if args.list_agents:
        list_agents()
        return

    # Require prompt for main execution
    if not args.prompt:
        parser.error("prompt is required unless using --test-cli or --list-agents")

    # Determine workspace directory
    if args.workspace:
        workspace_dir = Path(args.workspace).resolve()
    else:
        # Default: current working directory where command is executed
        workspace_dir = get_default_workspace()
    
    # Validate workspace directory
    try:
        validate_workspace(workspace_dir)
    except (FileNotFoundError, NotADirectoryError, ValueError, PermissionError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"📁 Workspace: {workspace_dir}")
    print(f"📁 Agent will have access to codebase in: {workspace_dir}\n")

    print("=" * 80)
    print("CURSOR AGENT CHAIN ORCHESTRATOR")
    print("=" * 80)
    print(f"Initial Prompt: {args.prompt}\n")

    # Plan creation phase (if requested)
    if args.plan or args.plan_only:
        create_plan(args.prompt, workspace_dir=workspace_dir)
        if args.plan_only:
            print("\n" + "=" * 80)
            print("✅ Plan-only mode: Exiting after plan creation")
            print("=" * 80)
            return

    # Phase 0: Splitter agent (unless skipped)
    splitter_result = None
    if not args.skip_splitter and not args.skip_prompt_engineering and not args.category:
        splitter_result = split_task(args.prompt, workspace_dir=workspace_dir)
        print(f"\n✅ Splitter Analysis:")
        print(f"   Requires multiple agents: {splitter_result.get('requires_multiple_agents', False)}")
        print(f"   Agents needed: {', '.join(splitter_result.get('agents_needed', []))}")
        print(f"   Strategy: {splitter_result.get('execution_strategy', 'sequential')}")
        print(f"   Summary: {splitter_result.get('summary', 'N/A')}\n")

    # Phase 0.5: Interactive Clarification (unless skipped)
    clarified_prompt = args.prompt
    if not args.skip_clarification and not args.skip_prompt_engineering and not args.category:
        clarified_prompt = interactive_clarification(args.prompt, workspace_dir=workspace_dir)
        preview = f"{clarified_prompt[:200]}..." if len(clarified_prompt) > 200 else clarified_prompt
        print(f"✅ Clarified Prompt: {preview}\n")
    elif args.skip_clarification:
        print("⏭️  Skipping clarification phase.\n")

    # Phase 1: Prompt engineering (unless skipped)
    if args.skip_prompt_engineering or args.category:
        perfected_prompt = clarified_prompt
        category = args.category or "other"
        print(f"⏭️  Skipping prompt engineering. Using category: {category}")
    else:
        perfected_prompt, category = perfect_prompt(clarified_prompt, workspace_dir=workspace_dir)
        print(f"\n✅ Categorized as: {category}")
        print(f"✅ Perfected Prompt: {perfected_prompt}\n")

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

    print("\n" + "=" * 80)
    print("✅ Agent chain completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
