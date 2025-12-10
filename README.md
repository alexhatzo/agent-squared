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

## MCP Integration (Cursor Chat)

**Use Agent² directly in Cursor's built-in chat!**

### Setup

1. **Install MCP library:**
   ```bash
   pip install -r mcp/requirements.txt
   ```

2. **Generate a Cursor API Key:**
   - Open Cursor Settings
   - Navigate to API Keys section
   - Generate a new API key

3. **Add to Cursor's MCP config** (`~/.cursor/mcp.json`):
   ```json
   {
     "mcpServers": {
       "agent-squared": {
         "command": "python",
         "args": ["/path/to/agent-squared/mcp/mcp_server.py"],
         "env": {
           "CURSOR_API_KEY": "your-cursor-api-key-here"
         }
       }
     }
   }
   ```

4. **Restart Cursor** to load the MCP server.

5. **Test the connection:**
   > "Use test_cursor_cli to check if everything is working"

### Usage in Chat

Once configured, you can use these tools in Cursor chat:

| Tool | Description |
|------|-------------|
| `agent_chain` | Run full pipeline (splitter → prompt engineer → specialists → composer) |
| `split_task` | Just analyze which agents are needed |
| `perfect_prompt` | Just optimize a prompt |
| `run_specialist` | Run a specific agent directly |
| `list_agents` | Show available specialists |
| `get_clarifying_questions` | Get questions to ask before executing |
| `test_cursor_cli` | Diagnose connection and API key issues |

**Example:** Just ask Cursor to use the agent_chain tool:
> "Use agent_chain to build a REST API with authentication and deploy to AWS"

---

## CLI Tool

For terminal usage without MCP integration.

### Quick Start

```bash
# Run from your project directory
cd cli
./chain-agents.sh "Build a login page with authentication"

# Or directly with Python
python cli/agent_chain.py "Create a REST API for user management"

# Interactive mode (opens Cursor UI)
python cli/agent_chain.py "Create a REST API" --interactive

# Plan-only mode (create plan without execution)
python cli/agent_chain.py "Design a microservices architecture" --plan-only
```

### CLI Options

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

---

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

---

## Project Structure

```
agent-squared/
├── cli/                    # CLI tool (uses Cursor CLI directly)
│   ├── agent_chain.py      # Core orchestrator
│   └── chain-agents.sh     # Shell wrapper
├── mcp/                    # MCP server (for Cursor chat integration)
│   ├── mcp_server.py       # MCP server
│   ├── agent_chain.py      # Orchestrator for MCP
│   ├── cursor-mcp-config.json  # Example MCP config
│   └── requirements.txt    # Python dependencies
├── agents/                 # Agent definitions (shared)
│   ├── splitter-agent.md
│   ├── prompt-engineer.md
│   ├── composer.md
│   └── ... (12+ specialists)
├── plans/                  # Generated plan documents
├── plan.md                 # Market analysis
└── README.md
```

## Requirements

- Python 3.7+
- Cursor CLI (`cursor agent` command)
- Cursor subscription
- **For MCP:** Cursor API Key (generate in Cursor Settings)

## License

MIT
