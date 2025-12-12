"""
Agent Chain package for Agent² system.

This package provides the multi-agent orchestration functionality:
- Task splitting and analysis
- Prompt engineering and optimization
- Specialist agent execution
- Multi-agent composition and integration

Example usage:
    from agent_chain import split_task, perfect_prompt, execute_agent
    
    # Analyze task
    result = split_task("Build a todo app")
    
    # Optimize prompt
    perfected, category = perfect_prompt("Build a todo app")
    
    # Execute agent
    output = execute_agent("frontend", perfected)
"""

# Core functions
from agent_chain.core import (
    set_mcp_mode,
    is_mcp_mode,
    run_cursor_agent,
    run_cursor_agent_detailed,
    load_agent_instructions,
    find_cursor_agent,
)

# Agent definitions
from agent_chain.agents import (
    AGENTS,
    ADDITIONAL_AGENTS,
    SPLITTER_AGENT,
    PROMPT_ENGINEER_AGENT,
    COMPOSER_AGENT,
    get_agent_config,
    get_all_agent_names,
    # Custom agents
    get_custom_agents,
    get_custom_agent_names,
    refresh_custom_agents,
    get_custom_agents_dir,
)

# Splitter functions
from agent_chain.splitter import split_task, SplitterResult

# Prompt engineering functions
from agent_chain.prompt_engineer import (
    perfect_prompt,
    generate_clarification_questions,
    has_enough_info,
)

# Executor functions
from agent_chain.executor import (
    execute_agent,
    execute_multiple_agents,
    execute_with_specialist,
    compose_integration,
)

# Planner functions
from agent_chain.planner import create_plan

__all__ = [
    # Core
    "set_mcp_mode",
    "is_mcp_mode",
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
    # Custom agents
    "get_custom_agents",
    "get_custom_agent_names",
    "refresh_custom_agents",
    "get_custom_agents_dir",
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
]
