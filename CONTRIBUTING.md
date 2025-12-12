# Contributing to Agent²

Thanks for your interest in contributing to Agent²! This document provides guidelines for contributing.

## Ways to Contribute

### 🐛 Report Bugs

Found a bug? Please open an issue with:

- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, Cursor version)

### 💡 Suggest Features

Have an idea? Open an issue with:

- Description of the feature
- Use case / why it would be helpful
- Any implementation ideas

### 🤖 Add New Agents

Want to add a new specialist agent?

1. Create a new `.md` file in `agents/`
2. Follow the format of existing agents (see `agents/backend-architect.md` as an example)
3. Add the agent to `mcp/agent_chain/agents.py` in `ADDITIONAL_AGENTS`
4. Submit a PR

**Agent file format:**

```markdown
---
name: my-agent-name
description: What this agent does
---

# My Agent

You are a specialized AI agent that...

## Your Expertise
- Skill 1
- Skill 2

## Guidelines
- How to approach tasks
- Best practices
```

### 🔧 Improve Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test with a local Cursor installation
5. Submit a PR

## Development Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/agent-squared.git
cd agent-squared

# Install dependencies
cd mcp
pip install -r requirements.txt

# Configure Cursor MCP (use absolute path)
# Edit ~/.cursor/mcp.json
```

## Code Style

- Python 3.10+ with type hints
- Use `ruff` for linting (if available)
- Follow existing code patterns
- Add docstrings to public functions

## Pull Request Process

1. Update documentation if needed
2. Test your changes locally
3. Describe what your PR does
4. Link any related issues

## Questions?

Open an issue or start a discussion!
