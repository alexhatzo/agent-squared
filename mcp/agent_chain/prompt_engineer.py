"""
Prompt engineering module for Agent² system.

This module provides functionality for:
- Perfecting and categorizing prompts
- Generating clarification questions
- Checking if enough information has been gathered
"""

from __future__ import annotations

import re
from pathlib import Path

from agent_chain.agents import PROMPT_ENGINEER_AGENT
from agent_chain.core import run_cursor_agent, load_agent_instructions, agent_print


def perfect_prompt(initial_prompt: str, workspace_dir: Path | None = None) -> tuple[str, str]:
    """
    Use prompt-engineer agent to perfect the prompt and categorize it.

    The prompt engineer will:
    1. Optimize the prompt for clarity and specificity
    2. Categorize it into a domain (frontend, backend, cloud, full-stack, other)

    Args:
        initial_prompt: The user's original prompt.
        workspace_dir: Optional workspace directory.

    Returns:
        Tuple of (perfected_prompt, category).
    """
    agent_print("🔧 Phase 1: Perfecting prompt with Prompt Engineer agent...")

    # Load prompt engineer instructions
    prompt_engineer_instructions = load_agent_instructions(
        PROMPT_ENGINEER_AGENT["file"], workspace_dir
    )

    # Create a specialized prompt for categorization
    categorization_prompt = f"""You are a prompt engineer. Your task is to:

1. Perfect and optimize this user prompt: "{initial_prompt}"

2. Categorize the perfected prompt into ONE of these categories:
   - frontend: UI components, React, styling, accessibility, client-side logic
   - backend: APIs, databases, server logic, microservices, data processing
   - cloud: Infrastructure, AWS, Kubernetes, Terraform, deployment, scaling
   - full-stack: Requires both frontend and backend work
   - other: Code review, Python optimization, documentation, etc.

3. Output your response in this EXACT format:

### Perfected Prompt
[Your perfected prompt here]

### Task Categorization
Category: [frontend|backend|cloud|full-stack|other]
Reason: [Brief explanation]

### Implementation Notes
[Your notes here]
"""

    output = run_cursor_agent(
        categorization_prompt,
        agent_context=prompt_engineer_instructions,
        model=PROMPT_ENGINEER_AGENT["model"],
        output_format="text",
        workspace_dir=workspace_dir,
    )

    agent_print("\n" + "=" * 80)
    agent_print("PROMPT ENGINEER OUTPUT:")
    agent_print("=" * 80)
    agent_print(output)
    agent_print("=" * 80 + "\n")

    # Parse output to extract perfected prompt and category
    perfected_prompt = _extract_section(output, "Perfected Prompt") or initial_prompt
    category = _extract_category(output) or "other"

    return perfected_prompt, category


def generate_clarification_questions(
    initial_prompt: str,
    accumulated_answers: dict[str, str] | None = None,
    workspace_dir: Path | None = None,
) -> tuple[list[str], str]:
    """
    Use prompt engineer agent to generate clarifying questions.

    Args:
        initial_prompt: The original user prompt.
        accumulated_answers: Dictionary of previous Q&A rounds.
        workspace_dir: Optional workspace directory.

    Returns:
        Tuple of (questions_list, analysis_text).
        Empty questions list means no clarification needed.
    """
    # Load prompt engineer instructions
    prompt_engineer_instructions = load_agent_instructions(
        PROMPT_ENGINEER_AGENT["file"], workspace_dir
    )

    # Build context from accumulated answers
    context_section = ""
    if accumulated_answers:
        context_section = "\n\n### Previous Clarifications:\n"
        for question, answer in accumulated_answers.items():
            context_section += f"Q: {question}\nA: {answer}\n"

    clarification_prompt = f"""You are a prompt engineer. Analyze this user prompt and determine what clarifying questions are needed to create the best possible prompt.

Original Prompt: "{initial_prompt}"
{context_section}

Your task:
1. Identify any ambiguities, missing details, or areas that need clarification
2. Generate specific, actionable questions that will help refine the prompt
3. If the prompt is already clear and complete, return an empty list

Output your response in this EXACT format:

### Questions Needed
[List each question on a new line, numbered 1., 2., 3., etc. If no questions needed, write "None"]

### Analysis
[Brief explanation of why these questions are needed, or why none are needed]
"""

    output = run_cursor_agent(
        clarification_prompt,
        agent_context=prompt_engineer_instructions,
        model=PROMPT_ENGINEER_AGENT["model"],
        output_format="text",
        workspace_dir=workspace_dir,
    )

    # Parse questions and analysis
    questions = _parse_questions(output)
    analysis = _extract_section(output, "Analysis") or ""

    return questions, analysis


def has_enough_info(
    initial_prompt: str,
    accumulated_answers: dict[str, str],
    workspace_dir: Path | None = None,
) -> bool:
    """
    Use prompt engineer agent to evaluate if enough information has been gathered.

    Args:
        initial_prompt: The original user prompt.
        accumulated_answers: Dictionary of all Q&A rounds.
        workspace_dir: Optional workspace directory.

    Returns:
        True if enough information to proceed, False otherwise.
    """
    # Load prompt engineer instructions
    prompt_engineer_instructions = load_agent_instructions(
        PROMPT_ENGINEER_AGENT["file"], workspace_dir
    )

    # Build context from accumulated answers
    context_section = "\n\n### Clarifications Received:\n"
    for question, answer in accumulated_answers.items():
        context_section += f"Q: {question}\nA: {answer}\n"

    completeness_prompt = f"""You are a prompt engineer. Evaluate if enough information has been gathered to create a comprehensive, actionable prompt.

Original Prompt: "{initial_prompt}"
{context_section}

Your task:
1. Assess if the original prompt combined with the clarifications provides enough detail
2. Determine if the information is sufficient to proceed with prompt engineering
3. Consider: Are there still critical ambiguities? Is the scope clear? Are technical requirements specified?

Output your response in this EXACT format:

### Enough Information?
[Yes or No]

### Reasoning
[Brief explanation of your assessment]
"""

    output = run_cursor_agent(
        completeness_prompt,
        agent_context=prompt_engineer_instructions,
        model=PROMPT_ENGINEER_AGENT["model"],
        output_format="text",
        workspace_dir=workspace_dir,
    )

    # Parse output to determine if enough info
    enough_section = _extract_section(output, "Enough Information?")
    if enough_section:
        return "yes" in enough_section.lower()

    return False


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def _extract_section(output: str, section_name: str) -> str | None:
    """Extract a section from markdown-formatted output."""
    pattern = rf"### {section_name}\s*\n(.*?)(?=\n###|$)"
    match = re.search(pattern, output, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_category(output: str) -> str | None:
    """Extract the category from prompt engineer output."""
    match = re.search(r"Category:\s*(\w+)", output, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None


def _parse_questions(output: str) -> list[str]:
    """Parse numbered questions from agent output."""
    questions = []

    questions_text = _extract_section(output, "Questions Needed")
    if not questions_text or questions_text.lower() == "none":
        return []

    # Extract numbered questions
    for line in questions_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove numbering (1., 2., etc.) and clean up
        cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
        if cleaned:
            questions.append(cleaned)

    return questions
