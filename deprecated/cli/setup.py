"""
Setup configuration for Agent² CLI package.

Installation:
    pip install -e .

This makes the CLI available as a system command 'agent-chain'.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README if available
readme_file = Path(__file__).parent.parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

setup(
    name="agent-squared-cli",
    version="0.1.0",
    description="Chain Cursor agents: Prompt Engineer → Specialist Agent(s)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Agent² Team",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        # No external dependencies - uses only Python standard library
    ],
    entry_points={
        "console_scripts": [
            "agent-chain=agent_chain.cli:main",
        ],
    },
    # Note: Agent files are resolved at runtime relative to the installed package location
    # See config.py and core.py for path resolution logic
)
