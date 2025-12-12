#!/usr/bin/env python3
"""
Agent Chain Orchestrator - Backward Compatible Entry Point

This module provides backward compatibility for importing from agent_chain.
All functionality has been moved to the agent_chain/ package.

Usage:
    # CLI usage
    python agent_chain.py "Your prompt here"
    python agent_chain.py --test-cli
    python agent_chain.py --list-agents
    
    # Programmatic usage  
    from agent_chain import split_task, perfect_prompt, execute_agent

Environment Variables:
    CURSOR_API_KEY: API key for Cursor CLI authentication
    CURSOR_MODEL: Model to use for all agents (default: composer-1)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add cli directory to path for package imports
sys.path.insert(0, str(Path(__file__).parent))

# Re-export everything from the agent_chain package for backward compatibility
from agent_chain import (
    # Core functions
    run_cursor_agent,
    run_cursor_agent_detailed,
    load_agent_instructions,
    find_cursor_agent,
    # Agent definitions
    AGENTS,
    ADDITIONAL_AGENTS,
    SPLITTER_AGENT,
    PROMPT_ENGINEER_AGENT,
    COMPOSER_AGENT,
    get_agent_config,
    get_all_agent_names,
    # Splitter
    split_task,
    SplitterResult,
    # Prompt engineering
    perfect_prompt,
    generate_clarification_questions,
    has_enough_info,
    # Executor
    execute_agent,
    execute_multiple_agents,
    execute_with_specialist,
    compose_integration,
    # Planner
    create_plan,
)

# For CLI usage
from agent_chain.cli import main, interactive_clarification, test_cursor_cli, list_agents

__all__ = [
    # Core
    "run_cursor_agent",
    "run_cursor_agent_detailed",
    "load_agent_instructions",
    "find_cursor_agent",
    # Agents
    "AGENTS",
    "ADDITIONAL_AGENTS",
    "SPLITTER_AGENT",
    "PROMPT_ENGINEER_AGENT",
    "COMPOSER_AGENT",
    "get_agent_config",
    "get_all_agent_names",
    # Splitter
    "split_task",
    "SplitterResult",
    # Prompt engineering
    "perfect_prompt",
    "generate_clarification_questions",
    "has_enough_info",
    # Executor
    "execute_agent",
    "execute_multiple_agents",
    "execute_with_specialist",
    "compose_integration",
    # Planner
    "create_plan",
    # CLI
    "main",
    "interactive_clarification",
    "test_cursor_cli",
    "list_agents",
]

if __name__ == "__main__":
    main()
