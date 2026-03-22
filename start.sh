#!/usr/bin/env bash
# start.sh — launch Agent Lab web UI
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$SCRIPT_DIR/agent"

# Prefer agent-local .venv; fall back to repo-root .venv
VENV="$AGENT_DIR/.venv"
if [ ! -f "$VENV/bin/python" ]; then
  VENV="$SCRIPT_DIR/.venv"
fi

if [ ! -f "$VENV/bin/python" ]; then
  echo ""
  echo "  Error: no Python virtual environment found."
  echo ""
  echo "  Set one up with:"
  echo "    cd agent"
  echo "    python3 -m venv .venv"
  echo "    .venv/bin/pip install -r requirements.txt"
  echo ""
  exit 1
fi

# Pick up WEB_PORT from agent/.env (if set), then fall back to 8000
ENV_FILE="$AGENT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  _port="$(grep -E '^WEB_PORT=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2 | tr -d '"' | tr -d "'" || true)"
  [ -n "$_port" ] && WEB_PORT="$_port"
fi
WEB_PORT="${WEB_PORT:-8000}"

echo ""
echo "  ◎  Agent Lab"
echo "  ─────────────────────────────────────────────"
echo "  Web UI   →  http://127.0.0.1:${WEB_PORT}"
echo "  Health   →  http://127.0.0.1:${WEB_PORT}/health"
echo "  WebSocket→  ws://127.0.0.1:${WEB_PORT}/ws"
echo "  Stop     →  Ctrl+C"
echo "  ─────────────────────────────────────────────"
echo ""

cd "$AGENT_DIR"
exec "$VENV/bin/python" -m uvicorn web_server:app \
  --host 127.0.0.1 \
  --port "$WEB_PORT" \
  --log-level info
