#!/usr/bin/env bash
set -euo pipefail

# Setup script for Vector DB MCP Service
# Adds MCP server config to Claude Code and Claude Desktop without overwriting existing settings

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Find a suitable Node.js binary (>= 20) ---
find_node() {
    # Check if node on PATH is >= 20
    if command -v node &>/dev/null; then
        local ver
        ver=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1)
        if [ "$ver" -ge 20 ] 2>/dev/null; then
            echo "node"
            return
        fi
    fi

    # Check nvm versions (highest first)
    if [ -d "$HOME/.nvm/versions/node" ]; then
        for dir in $(ls -rd "$HOME/.nvm/versions/node"/v{2[0-9],3[0-9]}* 2>/dev/null); do
            if [ -x "$dir/bin/node" ]; then
                echo "$dir/bin/node"
                return
            fi
        done
    fi

    # Check common Homebrew paths
    for bin in /opt/homebrew/bin/node /usr/local/bin/node; do
        if [ -x "$bin" ]; then
            local ver
            ver=$("$bin" -v 2>/dev/null | sed 's/v//' | cut -d. -f1)
            if [ "$ver" -ge 20 ] 2>/dev/null; then
                echo "$bin"
                return
            fi
        fi
    done

    return 1
}

# --- Ensure mcp-remote is installed for the found Node ---
ensure_mcp_remote() {
    local node_bin="$1"
    local node_dir
    node_dir="$(dirname "$node_bin")"
    local npm_bin="$node_dir/npm"
    local mcp_remote_bin="$node_dir/mcp-remote"

    if [ ! -x "$mcp_remote_bin" ]; then
        echo "Installing mcp-remote..."
        "$npm_bin" install -g mcp-remote 2>&1 | tail -1
    fi
    echo "$mcp_remote_bin"
}

# --- Merge JSON config without overwriting existing entries ---
# Requires python3 (available on macOS by default)
merge_mcp_config() {
    local config_file="$1"
    local server_name="$2"
    local server_json="$3"

    python3 - "$config_file" "$server_name" "$server_json" << 'PYEOF'
import json
import sys
import os

config_file = sys.argv[1]
server_name = sys.argv[2]
server_json = json.loads(sys.argv[3])

# Read existing config or start fresh
if os.path.exists(config_file):
    with open(config_file, 'r') as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            config = {}
else:
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    config = {}

# Ensure mcpServers key exists
if "mcpServers" not in config:
    config["mcpServers"] = {}

# Check if already configured
if server_name in config["mcpServers"]:
    print(f"  '{server_name}' already exists in {config_file} — skipping (delete it manually to reconfigure)")
    sys.exit(0)

# Add the new server
config["mcpServers"][server_name] = server_json

# Write back
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')

print(f"  Added '{server_name}' to {config_file}")
PYEOF
}

# ============================================================
echo "Vector DB MCP Service — Setup"
echo "=============================="
echo ""

# 1. Find Node.js >= 20
echo "Finding Node.js >= 20..."
NODE_BIN=$(find_node) || {
    echo "ERROR: Node.js >= 20 is required but not found."
    echo "Install it via: nvm install 22, or brew install node@22"
    exit 1
}
NODE_DIR="$(dirname "$(realpath "$NODE_BIN" 2>/dev/null || readlink -f "$NODE_BIN" 2>/dev/null || echo "$NODE_BIN")")"
echo "  Using: $NODE_BIN ($(${NODE_BIN} -v))"

# 2. Install mcp-remote if needed
echo ""
echo "Checking mcp-remote..."
MCP_REMOTE_BIN=$(ensure_mcp_remote "$NODE_BIN")
echo "  Using: $MCP_REMOTE_BIN"

# 3. Configure Claude Code (stdio — no proxy needed)
echo ""
echo "Configuring Claude Code..."
CLAUDE_CODE_CONFIG="$HOME/.claude/settings.json"
CLAUDE_CODE_JSON=$(cat << EOJSON
{
    "command": "docker",
    "args": ["exec", "-i", "vector-db-mcp-server", "python", "server.py", "--stdio"]
}
EOJSON
)
merge_mcp_config "$CLAUDE_CODE_CONFIG" "vector-db" "$CLAUDE_CODE_JSON"

# 4. Configure Claude Desktop (needs mcp-remote proxy with explicit node path)
echo ""
echo "Configuring Claude Desktop..."
CLAUDE_DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

# Use absolute paths to avoid nvm/PATH issues with Claude Desktop
CLAUDE_DESKTOP_JSON=$(cat << EOJSON
{
    "command": "${NODE_BIN}",
    "args": ["${MCP_REMOTE_BIN}", "http://localhost:11488/sse", "--allow-http"]
}
EOJSON
)
merge_mcp_config "$CLAUDE_DESKTOP_CONFIG" "vector-db" "$CLAUDE_DESKTOP_JSON"

# 5. Summary
echo ""
echo "Done! Next steps:"
echo "  1. Start the service:  cd $SCRIPT_DIR && docker compose up -d"
echo "  2. Restart Claude Desktop (Cmd+Q, then reopen)"
echo "  3. Claude Code picks up changes automatically"
echo ""
echo "Verify by asking Claude: \"List my vector DB namespaces\""
