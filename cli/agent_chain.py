#!/usr/bin/env python3
"""
Agent Chain Orchestrator

This script chains Cursor agents together:
1. Prompt Engineer agent perfects and categorizes the prompt
2. Appropriate specialist agent(s) execute the task

Usage:
    python agent-chain.py "Your initial prompt here"
    python agent-chain.py "Build a login page" --interactive
"""

import subprocess
import json
import re
import sys
import os
import argparse
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Agent definitions mapping
# Agent definitions - paths relative to project root (parent of cli/)
AGENTS = {
    "frontend": {
        "name": "frontend-developer",
        "file": "../agents/front-end-dev.md",
        "model": "composer-1"
    },
    "backend": {
        "name": "backend-architect",
        "file": "../agents/backend-architect.md",
        "model": "composer-1"
    },
    "cloud": {
        "name": "cloud-architect",
        "file": "../agents/cloud-architect.md",
        "model": "composer-1"
    },
    "full-stack": {
        "name": "full-stack",
        "agents": ["backend", "frontend"],
        "model": "composer-1"
    }
}

SPLITTER_AGENT = {
    "name": "splitter-agent",
    "file": "../agents/splitter-agent.md",
    "model": "composer-1"
}

PROMPT_ENGINEER_AGENT = {
    "name": "prompt-engineer",
    "file": "../agents/prompt-engineer.md",
    "model": "composer-1"
}

# Additional agents that can be invoked
ADDITIONAL_AGENTS = {
    "code-reviewer": {
        "name": "code-reviewer",
        "file": "../agents/code-reviewer.md",
        "model": "composer-1"
    },
    "python-pro": {
        "name": "python-pro",
        "file": "../agents/python-pro.md",
        "model": "composer-1"
    },
    "ui-ux-designer": {
        "name": "ui-ux-designer",
        "file": "../agents/ui-ux-designer.md",
        "model": "composer-1"
    },
    "security-engineer": {
        "name": "security-engineer",
        "file": "../agents/security-engineer.md",
        "model": "composer-1"
    },
    "ai-engineer": {
        "name": "ai-engineer",
        "file": "../agents/ai-engineer.md",
        "model": "composer-1"
    },
    "data-engineer": {
        "name": "data-engineer",
        "file": "../agents/data-engineer.md",
        "model": "composer-1"
    },
    "deployment-engineer": {
        "name": "deployment-engineer",
        "file": "../agents/deployment-engineer.md",
        "model": "composer-1"
    },
    "composer": {
        "name": "composer",
        "file": "../agents/composer.md",
        "model": "composer-1"
    }
}

# Composer agent for multi-agent integration validation
COMPOSER_AGENT = {
    "name": "composer",
    "file": "../agents/composer.md",
    "model": "composer-1"
}


def run_cursor_agent_detailed(prompt: str, agent_context: Optional[str] = None, model: str = "composer-1", 
                              print_output: bool = True, output_format: str = "text", 
                              workspace_dir: Optional[Path] = None, timeout: int = 600,
                              verbose: bool = False) -> Tuple[str, str, int]:
    """
    Run cursor agent CLI command with full details.
    
    Args:
        prompt: The prompt to send to the agent
        agent_context: Optional context/instructions for the agent
        model: Model to use
        print_output: Use --print flag for non-interactive mode
        output_format: Output format (text, json, stream-json)
        workspace_dir: Directory to run the command from (for codebase context)
        timeout: Timeout in seconds (default: 600)
        verbose: Print debug info
    
    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    cmd = ["cursor", "agent"]
    
    if print_output:
        cmd.append("--print")
        cmd.extend(["--output-format", output_format])
    
    cmd.extend(["--model", model])
    cmd.append("--force")  # Auto-approve commands
    
    # Build the full prompt with agent context
    full_prompt = prompt
    if agent_context:
        full_prompt = f"{agent_context}\n\nUser Request: {prompt}"
    
    cmd.append(full_prompt)
    
    if verbose:
        print(f"[DEBUG] Running: cursor agent --print ... (timeout={timeout}s)", file=sys.stderr)
    
    try:
        # Run from workspace directory so agent has access to codebase
        cwd = str(workspace_dir) if workspace_dir else None
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd  # Set working directory for codebase context
        )
        
        if result.returncode != 0:
            if verbose or result.stderr:
                print(f"Error running cursor agent (code {result.returncode}): {result.stderr}", file=sys.stderr)
        
        return result.stdout, result.stderr, result.returncode
        
    except subprocess.TimeoutExpired:
        error_msg = f"Agent execution timed out after {timeout} seconds"
        print(f"Error: {error_msg}", file=sys.stderr)
        return "", error_msg, -1
    except FileNotFoundError:
        error_msg = "Cursor CLI not found. Is 'cursor' in PATH? Run: cursor --version"
        print(f"Error: {error_msg}", file=sys.stderr)
        return "", error_msg, -2
    except Exception as e:
        error_msg = f"Error running cursor agent: {str(e)}"
        print(f"Error: {error_msg}", file=sys.stderr)
        return "", error_msg, -3


def run_cursor_agent(prompt: str, agent_context: Optional[str] = None, model: str = "composer-1", 
                     print_output: bool = True, output_format: str = "text", 
                     workspace_dir: Optional[Path] = None) -> str:
    """
    Run cursor agent CLI command (backward-compatible version).
    
    Returns:
        Agent output as string (stdout only)
    """
    stdout, stderr, code = run_cursor_agent_detailed(
        prompt, agent_context, model, print_output, output_format, workspace_dir
    )
    return stdout


def load_agent_instructions(agent_file: str, workspace_dir: Optional[Path] = None) -> str:
    """Load agent instructions from markdown file."""
    try:
        file_path = Path(agent_file)
        # If relative path, resolve relative to workspace or script directory
        if not file_path.is_absolute():
            if workspace_dir:
                file_path = workspace_dir / file_path
            else:
                # Default: relative to script directory
                file_path = Path(__file__).parent / file_path
        
        if file_path.exists():
            content = file_path.read_text()
            # Extract content after frontmatter
            if "---" in content:
                parts = content.split("---", 2)
                if len(parts) > 2:
                    return parts[2].strip()
            return content
    except Exception as e:
        print(f"Warning: Could not load agent file {agent_file}: {e}", file=sys.stderr)
    return ""


def split_task(initial_prompt: str, workspace_dir: Optional[Path] = None) -> Dict:
    """
    Use splitter agent to analyze the prompt and determine which agents are needed.
    
    Returns:
        Dictionary with splitter analysis (agents_needed, execution_strategy, etc.)
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
        workspace_dir=workspace_dir
    )
    
    print("\n" + "="*80)
    print("SPLITTER AGENT OUTPUT:")
    print("="*80)
    print(output)
    print("="*80 + "\n")
    
    # Try to extract JSON from output
    splitter_result = None
    
    # Try to find JSON in the output
    json_match = re.search(r'\{[\s\S]*\}', output)
    if json_match:
        try:
            splitter_result = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Fallback: if no JSON found, assume single agent
    if not splitter_result:
        print("⚠️  Could not parse splitter JSON. Defaulting to single agent workflow.")
        splitter_result = {
            "requires_multiple_agents": False,
            "agents_needed": [],
            "execution_strategy": "sequential",
            "execution_order": [],
            "dependencies": {},
            "summary": "Could not parse splitter output, using default"
        }
    
    return splitter_result


def create_plan(prompt: str, workspace_dir: Optional[Path] = None, agent_name: Optional[str] = None, focus: Optional[str] = None) -> Optional[Path]:
    """
    Create a plan document for the given prompt using prompt engineer agent.
    
    Args:
        prompt: The task prompt
        workspace_dir: Workspace directory
        agent_name: Optional agent name (for multi-agent plans)
        focus: Optional focus area for this agent
    
    Returns:
        Path to the created plan file, or None if creation failed
    """
    if agent_name:
        print(f"📋 Creating plan for {agent_name} agent...")
    else:
        print("📋 Creating plan document...")
    
    # Load prompt engineer instructions
    prompt_engineer_instructions = load_agent_instructions(PROMPT_ENGINEER_AGENT["file"], workspace_dir)
    
    # Build plan prompt with focus if provided
    if focus:
        plan_prompt = f"""You are a prompt engineer. Create a comprehensive plan document for this specific agent task:

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
        plan_prompt = f"""You are a prompt engineer. Create a comprehensive plan document for this task:

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
    
    output = run_cursor_agent(
        plan_prompt,
        agent_context=prompt_engineer_instructions,
        model=PROMPT_ENGINEER_AGENT["model"],
        output_format="text",
        workspace_dir=workspace_dir
    )
    
    if not output.strip():
        print("⚠️  Failed to generate plan content.")
        return None
    
    # Create plans directory if it doesn't exist
    # Plans dir is at project root (parent of cli/)
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent  # Go up from cli/ to agent-squared/
    
    if workspace_dir and (workspace_dir / "plans").exists():
        plans_dir = workspace_dir / "plans"
    else:
        plans_dir = project_root / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate plan filename
    if agent_name:
        plan_name = re.sub(r'[^a-zA-Z0-9\s-]', '', agent_name)[:30].strip().replace(' ', '-').lower()
        if not plan_name:
            plan_name = "agent"
    else:
        plan_name = re.sub(r'[^a-zA-Z0-9\s-]', '', prompt)[:50].strip().replace(' ', '-').lower()
        if not plan_name:
            plan_name = "plan"
    
    # Generate UUIDs for plan file (matching Cursor's format)
    plan_id = str(uuid.uuid4()).replace('-', '')
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    plan_filename = f"{plan_name}-{plan_id[:8]}.plan.md"
    plan_path = plans_dir / plan_filename
    
    # Create plan file with Cursor's format
    plan_uuid1 = str(uuid.uuid4())
    plan_uuid2 = str(uuid.uuid4())
    
    plan_title = f"{agent_name}: {prompt}" if agent_name else prompt
    
    plan_content = f"""<!-- {plan_uuid1} {plan_uuid2} -->
# {plan_title}
{f"## Focus: {focus}" if focus else ""}

{output}

---
*Plan created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*Plan ID: {plan_id[:8]}*
{f"*Agent: {agent_name}*" if agent_name else ""}
"""
    
    try:
        plan_path.write_text(plan_content)
        print(f"✅ Plan created: {plan_path}")
        return plan_path
    except Exception as e:
        print(f"⚠️  Failed to save plan: {e}", file=sys.stderr)
        return None


def generate_clarification_questions(initial_prompt: str, accumulated_answers: Dict[str, str] = None, 
                                     workspace_dir: Optional[Path] = None) -> Tuple[List[str], str]:
    """
    Use prompt engineer agent to generate clarifying questions.
    
    Args:
        initial_prompt: The original user prompt
        accumulated_answers: Dictionary of previous Q&A rounds
        workspace_dir: Optional workspace directory
    
    Returns:
        Tuple of (questions_list, analysis_text)
    """
    # Load prompt engineer instructions
    prompt_engineer_instructions = load_agent_instructions(PROMPT_ENGINEER_AGENT["file"], workspace_dir)
    
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
        workspace_dir=workspace_dir
    )
    
    # Parse output to extract questions
    questions = []
    analysis = ""
    
    # Try to extract questions section
    questions_match = re.search(r'### Questions Needed\s*\n(.*?)(?=\n###|$)', output, re.DOTALL)
    if questions_match:
        questions_text = questions_match.group(1).strip()
        if questions_text.lower() != "none" and questions_text.strip():
            # Extract numbered questions
            question_lines = [line.strip() for line in questions_text.split('\n') if line.strip()]
            for line in question_lines:
                # Remove numbering (1., 2., etc.) and clean up
                cleaned = re.sub(r'^\d+\.\s*', '', line).strip()
                if cleaned:
                    questions.append(cleaned)
    
    # Try to extract analysis section
    analysis_match = re.search(r'### Analysis\s*\n(.*?)(?=\n###|$)', output, re.DOTALL)
    if analysis_match:
        analysis = analysis_match.group(1).strip()
    
    return questions, analysis


def has_enough_info(initial_prompt: str, accumulated_answers: Dict[str, str], 
                   workspace_dir: Optional[Path] = None) -> bool:
    """
    Use prompt engineer agent to evaluate if enough information has been gathered.
    
    Args:
        initial_prompt: The original user prompt
        accumulated_answers: Dictionary of all Q&A rounds
        workspace_dir: Optional workspace directory
    
    Returns:
        Boolean indicating if enough info to proceed
    """
    # Load prompt engineer instructions
    prompt_engineer_instructions = load_agent_instructions(PROMPT_ENGINEER_AGENT["file"], workspace_dir)
    
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
        workspace_dir=workspace_dir
    )
    
    # Parse output to determine if enough info
    enough_info = False
    
    # Try to extract "Enough Information?" section
    enough_match = re.search(r'### Enough Information\?\s*\n(.*?)(?=\n###|$)', output, re.DOTALL)
    if enough_match:
        answer_text = enough_match.group(1).strip().lower()
        if "yes" in answer_text:
            enough_info = True
    
    return enough_info


def interactive_clarification(initial_prompt: str, workspace_dir: Optional[Path] = None) -> str:
    """
    Interactive clarification loop that asks questions until enough info is gathered.
    
    Args:
        initial_prompt: The original user prompt
        workspace_dir: Optional workspace directory
    
    Returns:
        Refined prompt with all answers incorporated
    """
    print("💬 Phase 0.5: Interactive Clarification...")
    print("="*80)
    print("The prompt engineer will ask clarifying questions to refine your prompt.")
    print("Answer each question, or type 'build' when ready to proceed.\n")
    
    accumulated_answers = {}
    current_prompt = initial_prompt
    round_number = 0
    
    try:
        while True:
            round_number += 1
            
            # Generate questions for this round
            questions, analysis = generate_clarification_questions(
                current_prompt, 
                accumulated_answers if accumulated_answers else None,
                workspace_dir
            )
            
            # If no questions and we have some answers, check if enough info
            if not questions:
                if accumulated_answers:
                    # Check if we have enough info
                    if has_enough_info(current_prompt, accumulated_answers, workspace_dir):
                        print("✅ Prompt engineer has enough information to proceed.\n")
                        break
                    else:
                        print("⚠️  No more questions, but information may still be incomplete.")
                        print("Type 'build' to proceed anyway, or provide additional context.\n")
                        # Get user input to proceed or provide more context
                        user_input = input("Your response (or 'build' to proceed): ").strip()
                        if user_input.lower() == "build":
                            print("\n🚀 Proceeding with current information...\n")
                            break
                        elif user_input:
                            # User provided additional context, incorporate it
                            accumulated_answers["Additional context"] = user_input
                            answers_section = "\n\n### Clarifications:\n"
                            for question, answer in accumulated_answers.items():
                                answers_section += f"- {question}: {answer}\n"
                            current_prompt = f"{initial_prompt}{answers_section}"
                            print(f"✅ Additional context recorded.\n")
                            continue  # Continue loop to generate new questions
                        else:
                            # Empty input, proceed anyway
                            print("Proceeding with current information...\n")
                            break
                else:
                    # No questions needed at all
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
            
            # Check if user wants to proceed
            if user_input.lower() == "build":
                print("\n🚀 Proceeding with current information...\n")
                break
            
            # If user provided input, store answers
            if user_input:
                # Store answers - if multiple questions, store the combined answer for all
                # The prompt engineer will see the context in the next round
                for question in questions:
                    accumulated_answers[question] = user_input
                
                # Build refined prompt incorporating answers
                answers_section = "\n\n### Clarifications:\n"
                for question, answer in accumulated_answers.items():
                    answers_section += f"- {question}: {answer}\n"
                
                current_prompt = f"{initial_prompt}{answers_section}"
                print(f"✅ Answer recorded. ({len(questions)} question(s) answered, {len(accumulated_answers)} total clarification(s))\n")
            else:
                print("⚠️  Empty input. Please provide an answer or type 'build' to proceed.\n")
        
        # Build final refined prompt
        if accumulated_answers:
            answers_section = "\n\n### Clarifications:\n"
            for question, answer in accumulated_answers.items():
                answers_section += f"- {question}: {answer}\n"
            refined_prompt = f"{initial_prompt}{answers_section}"
        else:
            refined_prompt = initial_prompt
        
        print("="*80)
        return refined_prompt
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Clarification interrupted by user.")
        print("Proceeding with current information...\n")
        # Build prompt with what we have
        if accumulated_answers:
            answers_section = "\n\n### Clarifications:\n"
            for question, answer in accumulated_answers.items():
                answers_section += f"- {question}: {answer}\n"
            return f"{initial_prompt}{answers_section}"
        return initial_prompt


def perfect_prompt(initial_prompt: str, workspace_dir: Optional[Path] = None) -> Tuple[str, str]:
    """
    Use prompt-engineer agent to perfect the prompt and categorize it.
    
    Returns:
        Tuple of (perfected_prompt, category)
    """
    print("🔧 Phase 1: Perfecting prompt with Prompt Engineer agent...")
    
    # Load prompt engineer instructions
    prompt_engineer_instructions = load_agent_instructions(PROMPT_ENGINEER_AGENT["file"], workspace_dir)
    
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
        workspace_dir=workspace_dir
    )
    
    print("\n" + "="*80)
    print("PROMPT ENGINEER OUTPUT:")
    print("="*80)
    print(output)
    print("="*80 + "\n")
    
    # Parse output to extract perfected prompt and category
    perfected_prompt = initial_prompt  # Fallback
    category = "other"  # Default
    
    # Try to extract perfected prompt
    prompt_match = re.search(r'### Perfected Prompt\s*\n(.*?)(?=\n###|$)', output, re.DOTALL)
    if prompt_match:
        perfected_prompt = prompt_match.group(1).strip()
    
    # Try to extract category
    category_match = re.search(r'Category:\s*(\w+)', output, re.IGNORECASE)
    if category_match:
        category = category_match.group(1).lower()
    
    return perfected_prompt, category


def execute_agent(agent_name: str, prompt: str, focus: str = "", interactive: bool = False,
                  workspace_dir: Optional[Path] = None) -> str:
    """
    Execute a single agent with the given prompt.
    
    Args:
        agent_name: Name of the agent to execute
        prompt: The prompt for the agent
        focus: Optional focus area for the agent
        interactive: Run in interactive mode
        workspace_dir: Workspace directory
    
    Returns:
        Agent output
    """
    # Build full prompt with focus if provided
    full_prompt = prompt
    if focus:
        full_prompt = f"{prompt}\n\nFocus: {focus}"
    
    # Map agent names to agent configs
    agent_config = None
    
    # Check main agents
    for key, agent in AGENTS.items():
        if agent["name"] == agent_name or key == agent_name:
            agent_config = agent
            break
    
    # Check additional agents
    if not agent_config and agent_name in ADDITIONAL_AGENTS:
        agent_config = ADDITIONAL_AGENTS[agent_name]
    
    if not agent_config:
        print(f"⚠️  Unknown agent: {agent_name}. Using default agent.")
        if interactive:
            subprocess.run(
                ["cursor", "agent", full_prompt],
                cwd=str(workspace_dir) if workspace_dir else None
            )
            return ""
        else:
            return run_cursor_agent(full_prompt, workspace_dir=workspace_dir)
    
    # Load agent instructions
    agent_instructions = load_agent_instructions(agent_config["file"], workspace_dir)
    
    if interactive:
        print(f"Opening {agent_config['name']} agent in Cursor...")
        subprocess.run(
            ["cursor", "agent", "--model", agent_config["model"], full_prompt],
            cwd=str(workspace_dir) if workspace_dir else None
        )
        return ""
    else:
        output = run_cursor_agent(
            full_prompt,
            agent_context=agent_instructions,
            model=agent_config["model"],
            workspace_dir=workspace_dir
        )
        print("\n" + "="*80)
        print(f"{agent_config['name'].upper().replace('-', ' ')} OUTPUT:")
        print("="*80)
        print(output)
        print("="*80 + "\n")
        return output


def execute_multiple_agents(splitter_result: Dict, perfected_prompt: str, 
                            interactive: bool = False, workspace_dir: Optional[Path] = None,
                            create_plans: bool = True):
    """
    Execute multiple agents based on splitter analysis.
    
    Args:
        splitter_result: Result from splitter agent analysis
        perfected_prompt: The perfected prompt
        interactive: Run in interactive mode
        workspace_dir: Workspace directory
        create_plans: Whether to create a plan for each agent before execution
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
        
        print(f"\n{'='*80}")
        print(f"Agent {i}/{len(execution_order)}: {agent_name}")
        print(f"Reason: {agent_reason}")
        if agent_focus:
            print(f"Focus: {agent_focus}")
        print(f"{'='*80}\n")
        
        # Create plan for this agent before execution (if requested)
        if create_plans:
            agent_plan_prompt = perfected_prompt
            if agent_focus:
                agent_plan_prompt = f"{perfected_prompt}\n\nFocus: {agent_focus}"
            
            plan_path = create_plan(
                agent_plan_prompt,
                workspace_dir=workspace_dir,
                agent_name=agent_name,
                focus=agent_focus
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
            workspace_dir=workspace_dir
        )


def compose_integration(agents_used: List[str], original_prompt: str, 
                        interactive: bool = False, workspace_dir: Optional[Path] = None) -> str:
    """
    Run the composer agent to validate that code from multiple agents integrates properly.
    
    Args:
        agents_used: List of agent names that were executed
        original_prompt: The original task prompt
        interactive: Run in interactive mode
        workspace_dir: Workspace directory
    
    Returns:
        Composer agent output
    """
    print("\n" + "="*80)
    print("🎼 Phase 3: Running Composer Agent for Integration Validation")
    print("="*80)
    print(f"Validating integration between: {', '.join(agents_used)}\n")
    
    # Load composer agent instructions
    composer_instructions = load_agent_instructions(COMPOSER_AGENT["file"], workspace_dir)
    
    # Build the composer prompt
    composer_prompt = f"""You are the integration composer. Multiple specialist agents have just completed work on this task:

**Original Task:** {original_prompt}

**Agents that contributed:**
{chr(10).join(f'- {agent}' for agent in agents_used)}

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
        subprocess.run(
            ["cursor", "agent", "--model", COMPOSER_AGENT["model"], composer_prompt],
            cwd=str(workspace_dir) if workspace_dir else None
        )
        return ""
    else:
        output = run_cursor_agent(
            composer_prompt,
            agent_context=composer_instructions,
            model=COMPOSER_AGENT["model"],
            workspace_dir=workspace_dir
        )
        print("\n" + "="*80)
        print("COMPOSER AGENT OUTPUT:")
        print("="*80)
        print(output)
        print("="*80 + "\n")
        return output


def execute_with_specialist(prompt: str, category: str, interactive: bool = False, 
                           workspace_dir: Optional[Path] = None):
    """
    Execute the task using the appropriate specialist agent(s).
    (Legacy function for single-agent execution)
    
    Args:
        prompt: The perfected prompt
        category: Task category (frontend, backend, cloud, full-stack, other)
        interactive: If True, run in interactive mode (opens Cursor UI)
    """
    print(f"\n🚀 Phase 2: Executing with {category} specialist agent(s)...\n")
    
    if category == "full-stack":
        # Execute backend first, then frontend
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
            print("Opening backend agent in Cursor...")
            subprocess.run(
                ["cursor", "agent", "--model", backend_agent["model"], backend_prompt],
                cwd=str(workspace_dir) if workspace_dir else None
            )
        else:
            output = run_cursor_agent(
                backend_prompt,
                agent_context=backend_instructions,
                model=backend_agent["model"],
                workspace_dir=workspace_dir
            )
            print("\n" + "="*80)
            print("BACKEND ARCHITECT OUTPUT:")
            print("="*80)
            print(output)
            print("="*80 + "\n")
        
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
            print("Opening frontend agent in Cursor...")
            subprocess.run(
                ["cursor", "agent", "--model", frontend_agent["model"], frontend_prompt],
                cwd=str(workspace_dir) if workspace_dir else None
            )
        else:
            output = run_cursor_agent(
                frontend_prompt,
                agent_context=frontend_instructions,
                model=frontend_agent["model"],
                workspace_dir=workspace_dir
            )
            print("\n" + "="*80)
            print("FRONTEND DEVELOPER OUTPUT:")
            print("="*80)
            print(output)
            print("="*80 + "\n")
        
        # Run composer to validate backend + frontend integration
        compose_integration(
            agents_used=["backend-architect", "frontend-developer"],
            original_prompt=prompt,
            interactive=interactive,
            workspace_dir=workspace_dir
        )
    
    elif category in AGENTS:
        agent = AGENTS[category]
        agent_instructions = load_agent_instructions(agent["file"], workspace_dir)
        
        if interactive:
            print(f"Opening {agent['name']} agent in Cursor...")
            subprocess.run(
                ["cursor", "agent", "--model", agent["model"], prompt],
                cwd=str(workspace_dir) if workspace_dir else None
            )
        else:
            output = run_cursor_agent(
                prompt,
                agent_context=agent_instructions,
                model=agent["model"],
                workspace_dir=workspace_dir
            )
            print("\n" + "="*80)
            print(f"{agent['name'].upper().replace('-', ' ')} OUTPUT:")
            print("="*80)
            print(output)
            print("="*80 + "\n")
    else:
        print(f"⚠️  Unknown category '{category}'. Running with default agent...")
        if interactive:
            subprocess.run(
                ["cursor", "agent", prompt],
                cwd=str(workspace_dir) if workspace_dir else None
            )
        else:
            output = run_cursor_agent(prompt, workspace_dir=workspace_dir)
            print("\n" + "="*80)
            print("AGENT OUTPUT:")
            print("="*80)
            print(output)
            print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Chain Cursor agents: Prompt Engineer → Specialist Agent(s)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Non-interactive mode (prints output to console)
  python agent-chain.py "Build a login page with authentication"
  
  # Interactive mode (opens Cursor UI for each agent)
  python agent-chain.py "Create a REST API for user management" --interactive
  
  # Skip prompt engineering (use original prompt directly)
  python agent-chain.py "Add dark mode to the app" --skip-prompt-engineering
        """
    )
    
    parser.add_argument(
        "prompt",
        help="Initial prompt/request"
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run agents in interactive mode (opens Cursor UI instead of printing output)"
    )
    
    parser.add_argument(
        "--skip-splitter",
        action="store_true",
        help="Skip splitter agent phase (go directly to prompt engineering)"
    )
    
    parser.add_argument(
        "--skip-prompt-engineering",
        action="store_true",
        help="Skip prompt engineering phase and go directly to specialist agent"
    )
    
    parser.add_argument(
        "--skip-clarification",
        action="store_true",
        help="Skip the interactive clarification phase (default: clarification enabled)"
    )
    
    parser.add_argument(
        "--category",
        choices=["frontend", "backend", "cloud", "full-stack", "other"],
        help="Force a specific category (skips categorization)"
    )
    
    parser.add_argument(
        "--workspace",
        type=str,
        help="Project workspace directory (default: parent of .cursor directory). The agent will have access to the codebase in this directory."
    )
    
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Create a plan document before execution (saved to .cursor/plans/)"
    )
    
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Only create a plan document, do not execute agents"
    )
    
    args = parser.parse_args()
    
    # Determine workspace directory
    if args.workspace:
        workspace_dir = Path(args.workspace).resolve()
        if not workspace_dir.exists():
            print(f"Error: Workspace directory does not exist: {workspace_dir}", file=sys.stderr)
            sys.exit(1)
        if not workspace_dir.is_dir():
            print(f"Error: Workspace path is not a directory: {workspace_dir}", file=sys.stderr)
            sys.exit(1)
    else:
        # Default: parent of .cursor directory (where script is located)
        workspace_dir = Path(__file__).parent.parent.resolve()
    
    print(f"📁 Workspace: {workspace_dir}")
    print(f"📁 Agent will have access to codebase in: {workspace_dir}\n")
    
    print("="*80)
    print("CURSOR AGENT CHAIN ORCHESTRATOR")
    print("="*80)
    print(f"Initial Prompt: {args.prompt}\n")
    
    # Plan creation phase (if requested)
    plan_path = None
    if args.plan or args.plan_only:
        plan_path = create_plan(args.prompt, workspace_dir=workspace_dir)
        if args.plan_only:
            print("\n" + "="*80)
            print("✅ Plan-only mode: Exiting after plan creation")
            print("="*80)
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
        print(f"✅ Clarified Prompt: {clarified_prompt[:200]}...\n" if len(clarified_prompt) > 200 else f"✅ Clarified Prompt: {clarified_prompt}\n")
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
    # When multiple agents are detected, always create plans for each agent
    # Also create plan if --plan flag is used
    create_agent_plans = args.plan or (splitter_result and splitter_result.get("requires_multiple_agents", False))
    
    if splitter_result and splitter_result.get("requires_multiple_agents", False):
        # Use multi-agent execution based on splitter analysis
        # Always create plans for each agent when multiple agents are detected
        execute_multiple_agents(splitter_result, perfected_prompt, 
                               interactive=args.interactive, workspace_dir=workspace_dir,
                               create_plans=create_agent_plans)
    else:
        # Use single-agent execution (legacy behavior)
        # Create plan if requested
        if create_agent_plans:
            create_plan(perfected_prompt, workspace_dir=workspace_dir, agent_name=category)
        execute_with_specialist(perfected_prompt, category, interactive=args.interactive, 
                               workspace_dir=workspace_dir)
    
    print("\n" + "="*80)
    print("✅ Agent chain completed!")
    print("="*80)


if __name__ == "__main__":
    main()

