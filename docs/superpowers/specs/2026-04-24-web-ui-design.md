# Web UI for Vector DB Service — Design

**Date:** 2026-04-24
**Status:** Approved for planning

## Goal

Add a local-first, Dockerized web interface to the existing vector DB service so users can browse namespaces, manage entries, run searches, and generate reports without going through Claude/MCP. The interface must be deployable as easily as the rest of the stack (single `docker compose up`).

## Non-goals (v1)

- Authentication / multi-user support. Out of scope; the service runs locally and writes are open from the host. The design leaves clean seams for adding auth later (single dependency point), but no login UI ships in v1.
- Persistent / saved reports. Reports are ephemeral — generated on each request, downloadable as CSV / JSON.
- PDF export.
- Realtime updates / websockets.
- Bulk import / export of entries.

## Constraints

- **Secrets hygiene:** DB credentials, internal hostnames, env config, and stack traces must never reach the browser. All errors are surfaced via a single error handler that returns user-safe messages.
- **No duplicate business logic:** the web layer reuses `mcp_server` modules directly (Python imports, not HTTP).
- **Same deploy story:** `docker compose up` brings up vector DB + MCP + web UI together.
- **No Node toolchain:** Tailwind, HTMX, and Alpine.js loaded via CDN. No build step.

## Architecture

### Repo layout

A new sibling package, `web_ui/`, lives alongside `mcp_server/`:

```
web_ui/
  Dockerfile
  pyproject.toml
  app/
    main.py              # FastAPI app, lifespan, exception handlers
    config.py            # Env vars (host/port + reuses mcp_server vars)
    deps.py              # FastAPI Depends: registry, storage, search, embedder
    errors.py            # AppError + safe-message handler
    routers/
      pages.py           # HTML routes
      api.py             # JSON /api/* mirror
    services/
      reports.py         # Report generation + CSV/JSON serializers
      validation.py      # Pydantic models for web input
    templates/
      base.html
      dashboard.html
      namespaces_list.html
      namespace_detail.html
      search.html
      report.html
      partials/          # HTMX fragments (rows, modals, errors)
    static/
      app.css
      app.js
tests/
  web_ui/
    test_api.py
    test_pages.py
    test_reports.py
    test_validation.py
```

### Code reuse (no duplication)

The web app imports the existing service classes directly:

- `mcp_server.namespaces.NamespaceRegistry`
- `mcp_server.storage.StorageManager` (extended with an `update()` method)
- `mcp_server.search.SearchManager`
- `mcp_server.embeddings.OllamaEmbedder`
- `mcp_server.schema.validate_payload`, `apply_embedding_template`

Both `mcp_server` and `web_ui` are installed in the web image so imports work.

### Docker

A new `web-ui` service joins `docker-compose.yml`:

- Builds from `web_ui/Dockerfile` (slim Python base, installs both packages)
- Mounts `./data/sqlite` (same as `mcp-server`) so the two services see the same registry
- Talks to `qdrant` and `ollama` over the docker network (same env vars as `mcp-server`)
- Default port `11489:11489` (one above MCP)
- `depends_on: [qdrant, ollama]`

The MCP server keeps running independently — the web UI is additive.

### Request lifecycle

1. Route handler receives request → resolves dependencies via `Depends`
2. Pydantic model validates query / form / JSON body
3. Service method called (existing `mcp_server` logic)
4. Render: `pages.py` returns `TemplateResponse`; `api.py` returns JSON
5. Errors → `AppError` → handler maps to safe message + status code

HTML routes call service methods directly (in-process), not through their own JSON API. This avoids a double network hop and keeps the JSON API as a clean, optional surface for future external clients.

## Pages and flows

### Top nav
Dashboard · Namespaces · Search · Reports

### 1. Dashboard (`/`)
- Cards: total namespaces, total entries (sum across collections), entries in `context`
- Table: namespaces with name, status, entry count, "View" / "Search" links

### 2. Namespace list (`/namespaces`)
- Same table with status filter and "New namespace" button
- New namespace form → `registry.create()` (status `proposed`)
- "Activate" action → `registry.confirm()`

### 3. Namespace detail (`/namespaces/{name}`)
Three tabs:

**Entries tab**
- Paginated table: `id`, `original_text` snippet, `entry_type`, `created_at`, key payload columns
- Per-row Edit / Delete
- "Add entry" modal with a form generated from the namespace's `fields` schema

**Config tab**
- View + edit `description`, `embedding_instructions`, `include_context`, `fields` array
- Reindex button → existing reindex logic
- Delete namespace with confirm dialog

**Stats tab**
- Count, vector dimension, oldest / newest entry timestamps

### 4. Search (`/search`)
- Form: query text, namespace selector (or "all"), top-k slider, optional metadata filters built from the selected namespace's filterable fields, score threshold
- Results table: rank, score, namespace, entry_type, snippet, key payload columns, created_at, "Open" link
- HTMX live-search: result table swaps in place; "Load more" appends rows; URL updates query params for shareable searches

### 5. Reports (`/reports`)
- Form fields:
  - `title` (required, ≤ 200 chars)
  - `namespace` (required)
  - Optional date range (`created_at` from / to)
  - Optional `entry_type` filter
  - Column picker (multi-select from payload fields + `id`, `created_at`, `original_text`, ≥ 1 required)
  - `max_rows` (default 1000, max 10000)
- Generate → titled HTML table with generated-at timestamp footer + CSV / JSON download buttons
- Reports are ephemeral; not stored

## Validation

Two layers, both required:

**Client-side hints**
- HTML5 attributes: `required`, `pattern`, `min`, `max`, `maxlength`
- Inline error messages via HTMX swap (no generic toast)

**Server-side (authoritative)**
- Pydantic models in `services/validation.py` for all form / JSON inputs (namespace create/update, entry create/update, search query, report request)
- Existing `mcp_server.schema.validate_payload` for entry payloads — keeps schema rules in one place
- Field-level errors returned as a structured map; templates render them next to the corresponding field

## Entry update mechanics

Qdrant points cannot be updated in place when the embedding changes. The new `StorageManager.update()` will:

1. Verify the point exists in the namespace's collection
2. Validate the new payload against the namespace schema
3. Apply the embedding template and regenerate the vector via Ollama
4. Overwrite the point with the same id (Qdrant `upsert`)
5. Preserve `created_at`; set `updated_at` to now (UTC, ISO 8601)

## JSON API contract

All endpoints return `application/json`. List endpoints return `{items, total, limit, offset}`.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/namespaces` | `?status=` filter |
| POST | `/api/namespaces` | Body: name, description, instructions, fields. Creates `proposed`. |
| GET | `/api/namespaces/{name}` | Config + stats |
| PATCH | `/api/namespaces/{name}` | Partial config update |
| POST | `/api/namespaces/{name}/confirm` | Activate |
| POST | `/api/namespaces/{name}/reindex` | Re-embed all entries |
| DELETE | `/api/namespaces/{name}` | Delete namespace + collection |
| GET | `/api/namespaces/{name}/entries` | `limit`, `offset`, `entry_type` |
| POST | `/api/namespaces/{name}/entries` | Create |
| GET | `/api/namespaces/{name}/entries/{id}` | Get |
| PUT | `/api/namespaces/{name}/entries/{id}` | Update (re-embed) |
| DELETE | `/api/namespaces/{name}/entries/{id}` | Delete |
| POST | `/api/search` | Body: query, namespace?, top_k, filters?, threshold? |
| POST | `/api/reports/generate` | Body: title, namespace, columns[], filters, format |

The HTML routes (`/`, `/namespaces`, `/namespaces/{name}`, `/search`, `/reports`) call the same service methods directly — they do not loop through the JSON API.

## Reports pipeline

1. `ReportRequest` Pydantic model validates (title length, ≥ 1 column, valid namespace, sane date range, `max_rows ≤ 10000`)
2. `services/reports.py` calls `qdrant.scroll()` on the namespace collection with payload + date filter, projects to chosen columns
3. Returns a `ReportResult` dataclass:
   - `title: str`
   - `generated_at: datetime` (UTC, ISO 8601 in output)
   - `namespace: str`
   - `columns: list[str]`
   - `rows: list[list[Any]]`
   - `row_count: int`
   - `filters_applied: dict`
4. Renderer dispatches:
   - `text/html` → `report.html` template (titled table, footer with timestamp + filters summary)
   - `text/csv` → streamed CSV; first lines are `# title: <title>` and `# generated_at: <iso>`, then header row, then data
   - `application/json` → JSON dump of `ReportResult`

## Error handling

A single `AppError(message: str, status_code: int)` exception type. A FastAPI exception handler:

- Maps `AppError` → JSON `{"error": message}` with the given status (for `/api/*`) or an HTML error partial (for HTMX requests, detected via `HX-Request` header) or a full error page (for non-HTMX HTML requests)
- Maps `ValidationError` → 422 with field-level error map
- Maps any other exception → logs server-side with full trace, returns generic "Internal error" to the client (no stack traces, no env data)

## Scalability hooks (built in from day one)

- Routes split into `pages.py` and `api.py` so a future SPA / external client can use the JSON API without touching HTML routes
- All list endpoints paginated (`limit` / `offset`)
- Service classes injected via `Depends` (testable, swappable)
- Async route handlers; sync Qdrant / Ollama calls run in the threadpool
- Config via env vars; no hardcoded paths or hosts
- Templates use partials so HTMX fragments and full pages share markup
- No global mutable state in `web_ui`

## Testing

- `tests/web_ui/` mirrors existing layout
- Unit tests on `services/reports.py` (filtering, projection, CSV/JSON serialization, timestamp formatting) and `services/validation.py`
- Integration tests via FastAPI `TestClient` against an in-memory SQLite + a Qdrant test fixture (reuse existing fixtures from `tests/`)
- Smoke test for each page route returning 200 with expected key strings
- New unit test for `StorageManager.update()` covering happy path + validation failure + missing-point error

## Documentation

- README gets a "Web UI" section: how to start, default URL (`http://localhost:11489`), screenshots optional
- `.env.example` updated with `WEB_UI_PORT` (default `11489`)

## Open questions

None at sign-off. Any future additions (auth, saved reports, PDF export, bulk import) are explicitly deferred.

## Commit plan

Implementation will land as a sequence of focused commits, roughly:

1. `feat(web-ui): scaffold FastAPI app, Docker service, base template`
2. `feat(web-ui): dashboard + namespace list pages`
3. `feat(web-ui): namespace detail with entries table + config view`
4. `feat(storage): add update() method on StorageManager` (with tests)
5. `feat(web-ui): entry CRUD (add / edit / delete) with validation`
6. `feat(web-ui): search page with filters and HTMX results`
7. `feat(web-ui): reports — HTML render + CSV/JSON export`
8. `feat(web-ui): scalability polish — JSON API, pagination, error handler`
9. `docs: README web UI section + .env.example update`

Each commit targets one of the user-listed feature areas (search, CRUD, reports, validation, scalability, GUI) so the history maps cleanly to the requirements.
