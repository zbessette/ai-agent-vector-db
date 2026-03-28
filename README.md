# Vector DB MCP Service

A local, Dockerized vector database with an MCP interface for Claude. Store, search, and manage domain-specific knowledge using RAG — all running locally with zero external API costs.

## Quick Start

```bash
git clone <repo-url>
cd vector-db-service
cp .env.example .env          # Optionally change MCP_SSE_PORT (default: 11488)
docker compose up -d          # First run pulls ~274MB embedding model
```

### Connect to Claude Code

Add to `~/.claude/settings.json`:

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

### Connect to Claude Desktop

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "vector-db": {
      "url": "http://localhost:11488/sse"
    }
  }
}
```

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
