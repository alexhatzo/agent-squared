#!/bin/bash
# Simple wrapper script for agent_chain.py
# Usage: ./chain-agents.sh "Your prompt here"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/agent_chain.py" "$@"



