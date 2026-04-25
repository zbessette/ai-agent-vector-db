# Vector DB MCP Service

A local, Dockerized vector database with an MCP interface for Claude. Store, search, and manage domain-specific knowledge using RAG — all running locally with zero external API costs.

## Quick Start

```bash
git clone <repo-url>
cd vector-db-service
cp .env.example .env          # Optionally change MCP_SSE_PORT (default: 11488)
docker compose up -d          # First run pulls ~274MB embedding model
./setup-mcp.sh                # Auto-configures Claude Code + Claude Desktop
```

The setup script:
- Finds Node.js >= 20 on your system (checks PATH, nvm, Homebrew)
- Installs `mcp-remote` if needed (required for Claude Desktop's SSE proxy)
- Adds the `vector-db` MCP server to both Claude Code and Claude Desktop configs
- Preserves any existing MCP servers in your config files (won't overwrite)

After running, restart Claude Desktop (Cmd+Q, reopen).

### Manual Setup

<details>
<summary>If you prefer to configure manually instead of using the setup script:</summary>

**Claude Code** — Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "vector-db": {
      "command": "docker",
      "args": ["exec", "-i", "vector-db-mcp-server", "python", "server.py", "--stdio"]
    }
  }
}
```

**Claude Desktop** — Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vector-db": {
      "command": "/absolute/path/to/node",
      "args": [
        "/absolute/path/to/mcp-remote",
        "http://localhost:11488/sse",
        "--allow-http"
      ]
    }
  }
}
```

**Important:** Claude Desktop does not use nvm or your shell profile. You must use absolute paths to `node` and `mcp-remote` binaries (e.g., `/Users/you/.nvm/versions/node/v22.21.1/bin/node`). The setup script handles this automatically.

</details>

## Web UI

A local web interface at `http://localhost:11489` (configurable via `WEB_UI_PORT`) for browsing namespaces, managing entries, running searches, and generating ad-hoc reports.

**Features:**
- **Dashboard** — namespace and entry counts at a glance
- **Namespaces** — create, view config, activate proposed namespaces, edit description/embedding instructions, delete
- **Entries** — paginated table per namespace; add, edit, delete entries with schema-driven forms
- **Search** — semantic search per namespace with score threshold and live HTMX results
- **Reports** — pick columns, date range, and entry-type filter; titled output with timestamp; CSV / JSON download

**Architecture notes:**
- Runs as the `web-ui` Docker service alongside `mcp-server`, sharing the SQLite namespace registry and Qdrant + Ollama backends
- Reuses the same Python service classes as the MCP server — no duplicate logic
- JSON `/api/*` endpoints mirror every page action so the UI is ready for future external clients or an SPA frontend
- Reindex from the web UI is a v1 placeholder (returns 501); use the MCP server's `reindex_namespace` tool from Claude

The web UI is additive — it does not affect the MCP server's behavior or replace its tool interface.

## What It Does

Claude gets persistent, searchable knowledge across conversations via these tools:

**Namespace Management:**
- `list_namespaces` — See all knowledge domains
- `get_namespace_config` — View schema and embedding instructions
- `propose_namespace` — Draft a new domain (Claude proposes, you approve)
- `confirm_namespace` — Activate a proposed namespace
- `update_namespace_config` — Change instructions or schema

**Data Operations:**
- `store_entry` — Store knowledge with validated metadata
- `search_entries` — Semantic search with automatic cross-cutting context
- `get_entry` / `delete_entry` — Retrieve or remove entries
- `list_entries` — Browse entries by metadata

**Maintenance:**
- `namespace_stats` — Collection metrics
- `reindex_namespace` — Re-embed all entries (after model/instruction changes)

## Architecture

Three Docker containers:

- **MCP Server** (Python) — Business logic, schema validation, tool interface
- **Qdrant** — Vector storage, one collection per namespace
- **Ollama** — Local embeddings via `nomic-embed-text` (768 dimensions)

A **SQLite** namespace registry stores schema definitions and embedding instructions, ensuring consistent data across Claude sessions.

A special **context** collection stores cross-cutting decisions (direction changes, preferences, patterns) and is automatically queried alongside domain searches.

## Configuration

Edit `.env` to customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_SSE_PORT` | `11488` | SSE endpoint port |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model name |
| `EMBEDDING_DIMENSIONS` | `768` | Vector dimensions |

## Data

All persistent data lives in `data/` (gitignored):
- `data/qdrant/` — Vector storage
- `data/sqlite/` — Namespace registry
- `data/ollama/` — Model cache

## Project Instructions & Skills

Example instructions you can add to Claude Desktop projects or CLAUDE.md files to teach Claude how to use the vector DB automatically:

| Template | Use case |
|----------|----------|
| [`examples/project-instructions/general-purpose.md`](examples/project-instructions/general-purpose.md) | Any project — search on task start, store decisions on completion, capture positive feedback |
| [`examples/project-instructions/code-project-with-jira.md`](examples/project-instructions/code-project-with-jira.md) | Code projects with Jira — adds ticket/commit storage workflow |
| [`examples/project-instructions/vector-db-first.md`](examples/project-instructions/vector-db-first.md) | Reduce context bloat — vector DB as primary knowledge source, static files as fallback |

Copy the instructions from any template into your Claude Desktop project's custom instructions or your project's CLAUDE.md file.

### Custom Skill

[`examples/skills/store-context.md`](examples/skills/store-context.md) — A `/store-context` skill for Claude Code that standardizes how decisions and ticket completions get captured. Supports interactive, decision, and ticket modes.

## Development

```bash
cd mcp_server
pip install -e ".[dev]"
pytest ../tests/ -v
```
