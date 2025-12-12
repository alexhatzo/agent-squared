"""
Utility tool handlers for Agent² MCP Server.

Utility tools:
- run_list_agents: List available agents
- run_get_clarifying_questions: Generate clarification questions
- run_check_task_readiness: Check if enough info gathered
"""

from __future__ import annotations

from typing import Any

from mcp.types import TextContent

from config import ToolName, WORKSPACE_DIR
from tools.registry import register_tool
from tools.pipeline import ensure_agent_chain_imported, run_with_timeout
from utils.output import OutputBuilder
from utils.helpers import get_workspace


@register_tool(ToolName.LIST_AGENTS)
async def run_list_agents(args: dict[str, Any]) -> list[TextContent]:
    """List all available specialist agents and their capabilities."""
    ac = ensure_agent_chain_imported()

    output = OutputBuilder()
    output.header("Core Agents")
    output.blank()
    for key, agent in ac.AGENTS.items():
        if "agents" not in agent:  # Skip composite agents
            output.bullet(f"**{key}** ({agent['name']})")

    output.blank()
    output.header("Additional Agents")
    output.blank()
    for key, agent in ac.ADDITIONAL_AGENTS.items():
        output.bullet(f"**{key}** ({agent['name']})")

    return [TextContent(type="text", text=output.build())]


@register_tool(ToolName.GET_CLARIFYING_QUESTIONS)
async def run_get_clarifying_questions(args: dict[str, Any]) -> list[TextContent]:
    """Generate clarifying questions for a task before execution."""
    from agent_chain import generate_clarification_questions

    prompt = args.get("prompt", "")
    previous_answers = args.get("previous_answers", {})

    result, error = await run_with_timeout(
        generate_clarification_questions,
        prompt,
        previous_answers if previous_answers else None,
        WORKSPACE_DIR,
        timeout_msg="Generating clarifying questions",
    )

    if error:
        troubleshooting = (
            "\n\n**Troubleshooting:**\n"
            "1. Check if Cursor CLI is authenticated: `cursor auth status`\n"
            "2. Try running manually: `cursor agent --print 'test'`\n"
            "3. The CLI may need to complete an interactive setup first"
        )
        return [TextContent(type="text", text=f"{error}{troubleshooting}")]

    questions, analysis = result

    if not questions:
        return [TextContent(
            type="text",
            text=(
                "✅ **No clarification needed.** The prompt is clear enough to proceed.\n\n"
                f"**Analysis:** {analysis}\n\n"
                "You can now call `agent_chain` with this prompt."
            ),
        )]

    output = OutputBuilder()
    output.header("Clarifying Questions")
    output.blank()
    output.add("Please ask the user these questions before proceeding:")
    output.blank()
    for i, q in enumerate(questions, 1):
        output.numbered(i, q)

    if analysis:
        output.blank()
        output.field("Why these questions matter", analysis)

    output.blank()
    output.separator()
    output.add("After getting answers, either:")
    output.bullet("Call `check_task_readiness` to verify enough info")
    output.bullet("Call `agent_chain` with the enriched prompt")

    return [TextContent(type="text", text=output.build())]


@register_tool(ToolName.CHECK_TASK_READINESS)
async def run_check_task_readiness(args: dict[str, Any]) -> list[TextContent]:
    """Check if enough information has been gathered to proceed with a task."""
    from agent_chain import has_enough_info

    prompt = args.get("prompt", "")
    answers = args.get("answers", {})

    if not answers:
        return [TextContent(
            type="text",
            text=(
                "⚠️ No answers provided. Call `get_clarifying_questions` first, "
                "then gather answers from the user."
            ),
        )]

    is_ready, error = await run_with_timeout(
        has_enough_info, prompt, answers, WORKSPACE_DIR,
        timeout_msg="Checking task readiness",
    )

    if error:
        return [TextContent(type="text", text=error)]

    if is_ready:
        # Build the enriched prompt
        enriched_lines = [prompt, "", "### Additional Context:"]
        for q, a in answers.items():
            enriched_lines.append(f"- {q}: {a}")
        enriched = "\n".join(enriched_lines)

        output = OutputBuilder()
        output.add("✅ **Ready to proceed!**")
        output.blank()
        output.add("Enough information has been gathered. Call `agent_chain` with this enriched prompt:")
        output.blank()
        output.code(enriched)

        return [TextContent(type="text", text=output.build())]
    else:
        return [TextContent(
            type="text",
            text=(
                "⚠️ **More information needed.**\n\n"
                "Consider asking more questions or proceeding with what you have.\n\n"
                "Call `get_clarifying_questions` again with the current answers to get follow-up questions, "
                "or call `agent_chain` if you want to proceed anyway."
            ),
        )]
