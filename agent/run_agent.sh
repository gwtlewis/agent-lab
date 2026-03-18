#!/bin/bash
# Script to run the Ollama Agent

VENV_PATH="/Users/lewisgong/code/.venv"
AGENT_DIR="/Users/lewisgong/code/agent-lab/agent"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Run the agent
cd "$AGENT_DIR"
echo "Starting Agent Lab - Ollama Agent"
echo "=================================="
$VENV_PATH/bin/python agent.py
