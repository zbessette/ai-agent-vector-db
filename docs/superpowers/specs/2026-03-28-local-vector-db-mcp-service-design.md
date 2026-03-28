# Local Vector DB MCP Service — Design Spec

## Overview

A local, Dockerized vector database service with an MCP (Model Context Protocol) interface that gives Claude (and other MCP-compatible agents) the ability to store, search, and manage domain-specific knowledge using RAG. Designed as a plug-and-play tool any developer can clone and run with a single `docker compose up`.

## Goals

- Provide Claude with persistent, searchable knowledge across conversations
- Support multiple isolated domains (MTG cards, Jira/code context, etc.) via separate Qdrant collections
- Capture decision-making context (direction changes, preferences, patterns) as cross-cutting knowledge
- Ensure embedding consistency through namespace-level instructions and schema validation
- Preserve all original text for future re-indexing if the embedding model changes
- Zero cost — all components run locally with no external API dependencies
- Plug-and-play distribution — clone, configure one env var if needed, `docker compose up`, add MCP config, done

## Non-Goals (v1)

- Automated ingestion (background workers, webhooks, event listeners)
- Migration of existing MD context files into the vector DB
- Multi-user or networked access (this is a local dev tool)
- LLM-driven summarization inside the MCP server (Claude handles summarization before calling store)

## Architecture

### Containers

Three containers orchestrated by Docker Compose:

```
┌──────────────────────────────────────────────────┐
│  docker-compose.yml                               │
│                                                   │
│  ┌──────────────┐  ┌───────────┐  ┌────────────┐ │
│  │  MCP Server   │  │  Qdrant   │  │  Ollama    │ │
│  │  (Python)     │──│  :6333    │  │  :11434    │ │
│  │  stdio + SSE  │  │  (int)    │  │  (int)     │ │
│  │               │──│           │  │  nomic-    │ │
│  │  SQLite (vol) │  │  (vol)    │  │  embed-    │ │
│  │  :11488 (SSE) │  │           │  │  text      │ │
│  └──────────────┘  └───────────┘  └────────────┘ │
└──────────────────────────────────────────────────┘
```

- **MCP Server (Python)** — `mcp` SDK, exposes tools over stdio (Claude Code) and SSE (Claude Desktop). Contains all business logic: namespace management, schema validation, embedding orchestration, dual-query merging. SQLite DB on a mounted volume.
- **Qdrant** — Vector storage. One collection per namespace plus one `context` collection. Port 6333 internal only (not exposed to host). Persistent volume.
- **Ollama** — Runs `nomic-embed-text` (768 dimensions, ~137M params). Port 11434 internal only. MCP server calls it over HTTP. Persistent volume for model cache. Auto-pulls model on first start.

### Connection to Claude

- **Claude Code (stdio):** `docker exec -i vector-db-mcp-server python server.py --stdio`
- **Claude Desktop (SSE):** `http://localhost:${MCP_SSE_PORT}/sse` (default 11488)

SSE port is configurable via `.env` to avoid conflicts with local dev servers.

## Data Model

### SQLite Schema — Namespace Registry

```sql
CREATE TABLE namespaces (
    id                    TEXT PRIMARY KEY,  -- UUID
    name                  TEXT UNIQUE NOT NULL,
    qdrant_collection     TEXT UNIQUE NOT NULL,
    description           TEXT,
    embedding_instructions TEXT NOT NULL,
    summary_instructions  TEXT,
    include_context       BOOLEAN DEFAULT 1,
    status                TEXT DEFAULT 'proposed',  -- proposed | active | archived
    created_at            TEXT NOT NULL,  -- ISO 8601
    updated_at            TEXT NOT NULL   -- ISO 8601
);

CREATE TABLE namespace_fields (
    id              TEXT PRIMARY KEY,  -- UUID
    namespace_id    TEXT NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
    field_name      TEXT NOT NULL,
    field_type      TEXT NOT NULL,  -- string, string[], int, float, bool
    required        BOOLEAN DEFAULT 0,
    description     TEXT,
    filterable      BOOLEAN DEFAULT 1,
    UNIQUE(namespace_id, field_name)
);
```

The SQLite DB is the source of truth for namespace configuration. It uses a clean, human-readable schema that can be edited directly via any SQLite client if needed. The Claude-driven MCP tools are the primary interface for v1, but the schema is designed to support direct manual editing as a future enhancement.

### Qdrant Entry Payload — Common Fields

Every entry in every collection includes these base fields:

| Field | Type | Description |
|-------|------|-------------|
| `original_text` | string | Full original text provided at storage time. Preserved for re-indexing. |
| `embedded_text` | string | Processed text actually used to generate the embedding. Produced by applying namespace `embedding_instructions` to `original_text` and other fields. |
| `entry_type` | string | Freeform type label: "card", "ticket", "commit", "decision", etc. |
| `source_id` | string or null | External identifier: Jira key, commit SHA, card name, etc. |
| `source_url` | string or null | Link back to origin system. |
| `tags` | string[] | Freeform tags for additional filtering. |
| `created_at` | string | ISO 8601 timestamp. |
| `updated_at` | string | ISO 8601 timestamp. |

Plus namespace-specific fields as defined in `namespace_fields`.

### Context Collection — Additional Fields

The `context` collection is a special namespace for cross-cutting decision knowledge. In addition to common fields, entries include:

| Field | Type | Description |
|-------|------|-------------|
| `related_namespaces` | string[] | Which namespaces this decision applies to. `["*"]` means universal. |
| `decision_type` | string | Category: "direction_change", "preference", "pattern", "constraint". |
| `reasoning` | string | Why this decision was made. |

The `context` collection has its own entry in the `namespaces` table with its own `embedding_instructions` (e.g., "embed the decision summary and reasoning together, focus on the problem being solved and the approach chosen").

### Example: MTG Card Payload

```json
{
    "original_text": "Sheoldred, the Apocalypse {2}{B}{B} Legendary Creature — Phyrexian Praetor. Deathtouch. Whenever you draw a card, you gain 2 life. Whenever an opponent draws a card, they lose 2 life. 4/5",
    "embedded_text": "Sheoldred, the Apocalypse. Legendary Creature — Phyrexian Praetor. Deathtouch. Whenever you draw a card, you gain 2 life. Whenever an opponent draws a card, they lose 2 life. 4/5. Synergies: card draw engines, lifegain payoffs, opponent punishment strategies.",
    "entry_type": "card",
    "source_id": "Sheoldred, the Apocalypse",
    "source_url": null,
    "tags": ["staple", "commander"],
    "created_at": "2026-03-28T12:00:00Z",
    "updated_at": "2026-03-28T12:00:00Z",
    "card_name": "Sheoldred, the Apocalypse",
    "colors": ["B"],
    "mana_cost": "{2}{B}{B}",
    "cmc": 4,
    "type_line": "Legendary Creature",
    "subtypes": ["Phyrexian", "Praetor"],
    "rarity": "mythic",
    "set": "DMU",
    "quantity": 2
}
```

## MCP Tool Surface

### Namespace Management

| Tool | Input | Description |
|------|-------|-------------|
| `list_namespaces` | — | Returns all namespaces with name, description, status, entry count. |
| `get_namespace_config` | `namespace` | Returns full config: schema, embedding instructions, field definitions. |
| `propose_namespace` | `name, description, embedding_instructions, summary_instructions?, fields[], include_context?` | Drafts a new namespace config. Stores in SQLite with status `proposed`. Returns config for user review. |
| `confirm_namespace` | `namespace` | Transitions status to `active`. Creates the Qdrant collection with proper field indexes. |
| `update_namespace_config` | `namespace, ...fields to update` | Modify embedding instructions, description, or field definitions on an existing namespace. Does not re-embed existing data. |

### Data Operations

| Tool | Input | Description |
|------|-------|-------------|
| `store_entry` | `namespace, original_text, entry_type, payload` | Validates required fields against namespace schema. Applies `embedding_instructions` to produce `embedded_text`. Calls Ollama to embed. Stores in Qdrant. |
| `search` | `namespace, query, filters?, limit?` | Semantic search. Embeds query via Ollama, searches target collection with optional payload filters. If `include_context` is true, dual-queries the `context` collection filtered by `related_namespaces` and merges results ranked by score. |
| `get_entry` | `entry_id` | Retrieve a specific entry by Qdrant point ID. |
| `delete_entry` | `entry_id` | Remove a specific entry by ID. |
| `list_entries` | `namespace, filters?, limit?, offset?` | Paginated listing with optional payload filters. No semantic search — browse/filter only. |

### Maintenance

| Tool | Input | Description |
|------|-------|-------------|
| `namespace_stats` | `namespace` | Entry count, last updated, embedding model info, storage size. |
| `reindex_namespace` | `namespace` | Re-generates embeddings for all entries using current `embedding_instructions` and embedding model. For model changes or instruction updates. |

### Update Pattern

Updates are handled as delete + re-store. No dedicated `update_entry` tool. Claude deletes the old entry and stores a new one.

## Internal Flows

### store_entry Flow

1. Look up namespace config from SQLite
2. Validate that namespace status is `active`
3. Validate payload has all required fields from `namespace_fields`
4. Apply `embedding_instructions` as a template to produce `embedded_text` from `original_text` and payload fields
5. Call Ollama (`nomic-embed-text`) to generate embedding from `embedded_text`
6. Store vector + full payload (including `original_text` and `embedded_text`) in Qdrant
7. Return entry ID

The MCP server does not call an LLM for summarization. If content needs summarization (e.g., long Jira tickets), Claude handles that in the conversation using the namespace's `summary_instructions` before calling `store_entry`. The server applies `embedding_instructions` as a deterministic template only.

### search Flow

1. Receive query text, namespace, optional filters
2. Embed query text via Ollama
3. Search target namespace's Qdrant collection (vector similarity + payload filters)
4. If namespace has `include_context = true`:
   a. Also search `context` collection where `related_namespaces` includes the target namespace name or `"*"`
   b. Merge results from both queries
   c. Deduplicate and rank by similarity score
5. Return ranked results with payloads

### propose_namespace → confirm_namespace Flow

1. Claude calls `propose_namespace` with config details
2. Server stores in SQLite with status `proposed`, does NOT create Qdrant collection yet
3. Claude presents the config to the user for review
4. User approves
5. Claude calls `confirm_namespace`
6. Server transitions status to `active`, creates Qdrant collection with vector config (768 dims for nomic-embed-text) and payload field indexes based on `namespace_fields` where `filterable = true`

## Repository Structure

```
vector-db-service/
├── docker-compose.yml
├── .env                          # MCP_SSE_PORT=11488, EMBEDDING_MODEL=nomic-embed-text
├── .env.example                  # Template for devs to copy
├── .gitignore
├── README.md
├── mcp_server/
│   ├── Dockerfile
│   ├── pyproject.toml            # mcp, qdrant-client, httpx, pydantic
│   ├── server.py                 # Entrypoint, MCP tool registration, stdio/SSE modes
│   ├── namespaces.py             # SQLite namespace registry CRUD
│   ├── embeddings.py             # Ollama HTTP client wrapper
│   ├── search.py                 # Search + dual-query merge logic
│   ├── storage.py                # Store/delete/list entry operations
│   └── schema.py                 # Payload validation against namespace_fields
├── data/                         # Gitignored — all persistent state
│   ├── qdrant/                   # Qdrant volume
│   ├── sqlite/                   # SQLite DB volume
│   └── ollama/                   # Model cache volume
└── docs/
```

## Configuration

### .env

```env
MCP_SSE_PORT=11488
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSIONS=768
QDRANT_HOST=qdrant
QDRANT_PORT=6333
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
```

### Claude Code MCP Config

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

### Claude Desktop MCP Config

```json
{
    "mcpServers": {
        "vector-db": {
            "url": "http://localhost:11488/sse"
        }
    }
}
```

## First-Run Experience

```bash
git clone <repo-url>
cp .env.example .env          # Optionally change MCP_SSE_PORT
docker compose up -d          # Starts Qdrant, Ollama, MCP server
# Ollama auto-pulls nomic-embed-text on first start (~274MB, one-time download)
# Add MCP config to Claude Code or Claude Desktop
# Done — Claude now has vector DB tools available
```

## Re-indexing Strategy

All original text is preserved in the `original_text` payload field. The `embedded_text` field records what was actually embedded. If the embedding model or namespace `embedding_instructions` change:

1. Call `reindex_namespace` for the affected namespace
2. Server iterates all entries, re-applies `embedding_instructions` to produce new `embedded_text`
3. Calls Ollama with the current model to generate new embeddings
4. Overwrites vectors in Qdrant while preserving all payload data

This is a full rewrite of every vector in the collection. For hundreds to low thousands of entries, this completes in minutes. For tens of thousands, it may take longer.

## Post-Build Deliverable

After implementation is complete, propose:

1. **Claude Desktop project instructions** for integrating the vector DB into daily workflow, including a "vector DB first, MD files as fallback" variant that reduces context bloat
2. **A custom skill** that automates the store-on-positive-feedback pattern and teaches Claude when/how to query the vector DB during task work

## Open Considerations

- **Embedding model drift:** Switching models requires full re-index of all namespaces. The `reindex_namespace` tool handles this, but it's a bulk operation.
- **MD file migration:** Current context library at `/Users/ZBessette/dev/contexts/` serves static reference well. Over time, accumulated knowledge in those files could be migrated to the vector DB, leaving only stable project facts in MD. This is a future effort, not v1 scope.
- **Manual SQLite editing:** The schema is designed to be human-readable and directly editable. A future enhancement could add a CLI or web UI for namespace management outside of Claude.
- **Multi-repo domains:** A domain like `hub-ecosystem` can span multiple GitHub repos and Jira projects. The namespace is a logical grouping — entries from different repos coexist in the same collection, differentiated by `source_id` and `source_url` metadata.
