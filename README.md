# Agent² (Agent Squared)

> Meta-orchestration layer that chains specialized AI agents together for complex development workflows.

## How It Works

```
Your Prompt → Splitter → Prompt Engineer → Specialist Agent(s) → Composer → Result
                ↓              ↓                    ↓                ↓
         Decompose task   Perfect prompt    Execute tasks    Validate integration
```

When multiple agents are used, the **Composer** agent runs at the end to:
- Verify API contracts between frontend/backend
- Check data flow consistency
- Fix integration issues
- Add any missing glue code

---

## 🔌 Cursor Integration (MCP)

**Use Agent² directly in Cursor's built-in chat!**

### Setup

1. **Install MCP library:**
   ```bash
   pip install mcp
   ```

2. **Add to Cursor's MCP config** (`~/.cursor/mcp.json`):
   ```json
   {
     "mcpServers": {
       "agent-squared": {
         "command": "python",
         "args": ["/path/to/agent-squared/mcp_server.py"],
         "env": {}
       }
     }
   }
   ```

3. **Restart Cursor** to load the MCP server.

### Usage in Chat

Once configured, you can use these tools in Cursor chat:

| Tool | Description |
|------|-------------|
| `agent_chain` | Run full pipeline (splitter → prompt engineer → specialists) |
| `split_task` | Just analyze which agents are needed |
| `perfect_prompt` | Just optimize a prompt |
| `run_specialist` | Run a specific agent directly |
| `list_agents` | Show available specialists |

**Example:** Just ask Cursor to use the agent_chain tool:
> "Use agent_chain to build a REST API with authentication and deploy to AWS"

---

## CLI Quick Start

```bash
# Run from your project directory
python /path/to/agent-squared/agent_chain.py "Build a login page with authentication"

# Interactive mode (opens Cursor UI)
python agent_chain.py "Create a REST API for user management" --interactive

# Plan-only mode (create plan without execution)
python agent_chain.py "Design a microservices architecture" --plan-only
```

## Available Agents

| Agent | Focus |
|-------|-------|
| `frontend-developer` | React, UI components, styling, accessibility |
| `backend-architect` | APIs, databases, microservices |
| `cloud-architect` | AWS, Terraform, Kubernetes, deployment |
| `code-reviewer` | Code quality, security, maintainability |
| `python-pro` | Python optimization, testing, async |
| `ui-ux-designer` | User research, wireframes, design systems |
| `security-engineer` | API security, audits, compliance |
| `ai-engineer` | LLM integration, RAG systems, agents |
| `data-engineer` | Data pipelines, ETL, analytics |
| `deployment-engineer` | CI/CD, containers, orchestration |
| `composer` | Integration validation (auto-runs after multi-agent tasks) |

## Options

```
--interactive              Opens Cursor UI for each agent
--skip-splitter           Skip task decomposition
--skip-prompt-engineering Skip prompt optimization
--skip-clarification      Skip interactive Q&A phase
--category CATEGORY       Force category (frontend|backend|cloud|full-stack|other)
--workspace DIR           Specify project directory
--plan                    Create plan document before execution
--plan-only               Only create plan, don't execute
```

## Examples

```bash
# Simple frontend task
python agent_chain.py "Create a responsive navbar"

# Full-stack (auto-detected, runs backend → frontend)
python agent_chain.py "Build a todo app with authentication"

# Multi-agent with deployment (backend → cloud)
python agent_chain.py "Create user API and deploy to AWS EKS"

# Parallel agents (code review + optimization)
python agent_chain.py "Review auth code and optimize database queries"
```

## Requirements

- Python 3.7+
- Cursor CLI (`cursor agent` command)
- Cursor subscription (BYOK - uses your existing account)

## Project Structure

```
agent-squared/
├── agent_chain.py      # Core orchestrator
├── mcp_server.py       # MCP server for Cursor integration
├── chain-agents.sh     # Shell wrapper
├── cursor-mcp-config.json  # Example MCP config
├── agents/             # Agent definitions
│   ├── splitter-agent.md
│   ├── prompt-engineer.md
│   └── ... (12+ specialists)
├── plans/              # Generated plans
├── plan.md             # Market analysis
└── README.md
```

## License

MIT

