# Agent² (Agent Squared)

> Multi-agent orchestration for Cursor – chain specialized AI agents together for complex development workflows.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## What is Agent²?

Agent² is an MCP (Model Context Protocol) server that extends Cursor with multi-agent capabilities. Instead of handling everything with a single prompt, Agent² intelligently routes your task through specialized agents:

```
Your Task → Splitter → Prompt Engineer → Specialist Agent(s) → Composer → Result
              ↓              ↓                    ↓                ↓
        Decompose       Optimize           Execute work      Validate
        the task        the prompt         (frontend,        integration
                                           backend, etc.)
```

## Quick Start

test 

### 1. Install Dependencies

```bash
cd mcp
pip install -r requirements.txt
```

### 2. Get Your Cursor API Key

1. Open **Cursor Settings** (Cmd/Ctrl + ,)
2. Go to **Features** → **API Keys**
3. Generate a new API key

### 3. Configure MCP

Add to your Cursor MCP config at `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "agent-squared": {
      "command": "python",
      "args": ["/path/to/agent-squared/mcp/mcp_server.py"],
      "env": {
        "CURSOR_API_KEY": "your-cursor-api-key-here",
        "CURSOR_MODEL": "composer-1"
      }
    }
  }
}
```

### 4. Restart Cursor

Restart Cursor to load the MCP server.

### 5. Start Using Agent²

In Cursor chat, just say:

> **"Use agent_squared to build a REST API with authentication"**

Or test the connection first:

> **"Use test_cursor_mcp to check if agent_squared is working"**

---

## Usage Examples

### Simple Task
>
> "Use agent_squared to add dark mode toggle to the settings page"

### Complex Full-Stack Task
>
> "Use agent_squared to build a user dashboard with:
>
> - Backend API for user stats
> - React frontend with charts
> - Authentication middleware"

### Infrastructure Task
>
> "Use agent_squared to set up CI/CD pipeline with GitHub Actions and deploy to AWS ECS"

---

## Available Agents

| Agent | Specialization |
|-------|----------------|
| `frontend` | React, UI components, styling, accessibility |
| `backend` | APIs, databases, microservices, server logic |
| `cloud` | AWS, Terraform, Kubernetes, deployment |
| `code-reviewer` | Code quality, security review, best practices |
| `python-pro` | Python optimization, async patterns, testing |
| `ui-ux-designer` | User research, wireframes, design systems |
| `security-engineer` | API security, audits, compliance |
| `ai-engineer` | LLM integration, RAG systems, AI agents |
| `data-engineer` | Data pipelines, ETL, analytics |
| `deployment-engineer` | CI/CD, containers, orchestration |

### Adding Custom Agents

You can add your own specialized agents by creating `.md` files in the `agents/` folder. Any markdown file not already mapped to a built-in agent will be automatically discovered.

**1. Create your agent file:**

```bash
# Create agents/my-agent.md
touch agents/my-agent.md
```

**2. Add frontmatter and instructions:**

```markdown
---
name: my-agent
description: Brief description of what your agent does (used by the splitter)
tools: Read, Write, Edit, Bash
model: sonnet
---

You are a specialist in [your domain].

When given a task, you should:
1. [Your approach]
2. [Your approach]

[Additional instructions...]
```

**3. Restart Cursor** to reload the MCP server

**4. Verify it's discovered:**

> "Use list_agents to show available agents"

Your custom agent will appear under **Custom Agents** and the splitter will automatically recommend it when relevant based on your description.

---

## MCP Tools Reference

| Tool | Description |
|------|-------------|
| `agent_squared` | **Main entry point** – just describe your task |
| `split_task` | Analyze which agents are needed |
| `perfect_prompt` | Optimize a prompt |
| `run_specialist` | Run a specific agent |
| `compose_agents` | Validate multi-agent integration |
| `list_agents` | Show available specialists |
| `test_cursor_mcp` | Diagnose connection issues |

### Step-by-Step Control

For more control over the pipeline, you can call tools individually:

1. `split_task` – See which agents are needed
2. `perfect_prompt` – Optimize the task description
3. `run_specialist` – Execute each agent
4. `compose_agents` – Validate integration

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CURSOR_API_KEY` | Yes | Your Cursor API key |
| `CURSOR_MODEL` | No | Model to use (default: `composer-1`) |

### Custom Model

To use a different model:

```json
{
  "mcpServers": {
    "agent-squared": {
      "command": "python",
      "args": ["/path/to/agent-squared/mcp/mcp_server.py"],
      "env": {
        "CURSOR_API_KEY": "your-key",
        "CURSOR_MODEL": "claude-sonnet-4"
      }
    }
  }
}
```

---

## Project Structure

```
agent-squared/
├── mcp/                      # MCP server implementation
│   ├── mcp_server.py         # Main MCP server
│   ├── agent_chain/          # Agent orchestration logic
│   ├── tools/                # MCP tool handlers
│   ├── utils/                # Helper utilities
│   └── requirements.txt      # Python dependencies
├── agents/                   # Agent instruction files
│   ├── splitter-agent.md
│   ├── prompt-engineer.md
│   ├── composer.md
│   └── ... (specialist agents)
└── README.md
```

---

## How It Works

### The Pipeline

1. **Splitter Agent** analyzes your task and determines which specialists are needed
2. **Prompt Engineer** optimizes your prompt for clarity and specificity
3. **Specialist Agents** execute the actual work (coding, infrastructure, etc.)
4. **Composer Agent** validates that all pieces integrate correctly

### Why Multi-Agent?

Single prompts hit walls on complex tasks. By decomposing work across specialized agents:

- Each agent has focused expertise and instructions
- Complex tasks are broken into manageable pieces
- Integration is explicitly validated
- You get better results than one-shot prompting

---

## Troubleshooting

### "Agent execution timed out"

1. Run `test_cursor_mcp` to check your setup
2. Verify your `CURSOR_API_KEY` is valid
3. Check that `cursor-agent` is installed: `which cursor-agent`

### "cursor-agent not found"

Install the Cursor CLI:

```bash
curl https://cursor.com/install -fsS | bash
```

### Tools not appearing in Cursor

1. Check `~/.cursor/mcp.json` syntax
2. Verify the path to `mcp_server.py` is correct
3. Restart Cursor completely

---

## Contributing

Contributions welcome! Feel free to:

- Add new specialist agents
- Improve existing agent instructions
- Fix bugs or improve error handling
- Add documentation

---

## License

MIT License - see [LICENSE](LICENSE) for details.
