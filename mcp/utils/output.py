"""
Output formatting utilities for Agent² MCP Server.

Provides the OutputBuilder class for constructing structured markdown output.
"""

from __future__ import annotations


class OutputBuilder:
    """
    Helper class for building structured markdown output.

    Example:
        output = OutputBuilder()
        output.header("Step Complete")
        output.field("Status", "Success")
        output.separator()
        return output.build()
    """

    def __init__(self) -> None:
        self._lines: list[str] = []

    def add(self, text: str) -> "OutputBuilder":
        """Add a line of text."""
        self._lines.append(text)
        return self

    def blank(self) -> "OutputBuilder":
        """Add a blank line."""
        self._lines.append("")
        return self

    def header(self, text: str, level: int = 2) -> "OutputBuilder":
        """Add a markdown header."""
        self._lines.append(f"{'#' * level} {text}")
        return self

    def field(self, name: str, value: str) -> "OutputBuilder":
        """Add a field in bold name: value format."""
        self._lines.append(f"**{name}**: {value}")
        return self

    def bullet(self, text: str) -> "OutputBuilder":
        """Add a bullet point."""
        self._lines.append(f"- {text}")
        return self

    def numbered(self, number: int, text: str) -> "OutputBuilder":
        """Add a numbered item."""
        self._lines.append(f"{number}. {text}")
        return self

    def code(self, text: str, language: str = "") -> "OutputBuilder":
        """Add a code block."""
        self._lines.append(f"```{language}")
        self._lines.append(text)
        self._lines.append("```")
        return self

    def separator(self) -> "OutputBuilder":
        """Add a horizontal rule."""
        self._lines.append("---")
        return self

    def build(self) -> str:
        """Build the final output string."""
        return "\n".join(self._lines)
