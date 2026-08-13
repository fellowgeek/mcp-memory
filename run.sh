#!/usr/bin/env bash
set -e

# Capture caller's working directory before changing to server directory (ignore root '/')
if [ -z "$MCP_MEMORY_PROJECT_ROOT" ]; then
    CURRENT_PWD="$(pwd)"
    if [ "$CURRENT_PWD" != "/" ] && [ -n "$CURRENT_PWD" ]; then
        export MCP_MEMORY_PROJECT_ROOT="$CURRENT_PWD"
    fi
fi

# Resolve server installation directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
VENV_DIR="$DIR/.venv"

# Create .venv if it does not exist
if [ ! -d "$VENV_DIR" ]; then
    echo "[mcp-memory] Creating virtual environment in $VENV_DIR..." >&2
    python3 -m venv "$VENV_DIR"
    echo "[mcp-memory] Installing dependencies from requirements.txt..." >&2
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip >&2
    "$VENV_DIR/bin/pip" install --quiet -r "$DIR/requirements.txt" >&2
    echo "[mcp-memory] Virtual environment successfully initialized." >&2
fi

# Execute server using the virtual environment python
exec "$VENV_DIR/bin/python" "$DIR/memory_server.py" "$@"
