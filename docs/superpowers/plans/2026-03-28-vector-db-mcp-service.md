# Vector DB MCP Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, Dockerized vector DB MCP server that gives Claude persistent, searchable knowledge across conversations via Qdrant + Ollama.

**Architecture:** Python MCP server (FastMCP) exposing tools over stdio + SSE. Qdrant for vector storage (one collection per namespace). Ollama for local embeddings (nomic-embed-text, 768 dims). SQLite namespace registry for schema/config. All three services orchestrated by Docker Compose.

**Tech Stack:** Python 3.12, mcp SDK (FastMCP), qdrant-client, httpx, sqlite3, pytest, Docker Compose

**Spec:** `docs/superpowers/specs/2026-03-28-local-vector-db-mcp-service-design.md`

---

## File Structure

```
vector-db-service/
├── docker-compose.yml              # Orchestrates Qdrant, Ollama, MCP server
├── .env.example                    # Default config template
├── .gitignore                      # Ignore data/, __pycache__, .env
├── README.md                       # Setup and usage guide
├── mcp_server/
│   ├── Dockerfile                  # Python 3.12 slim image
│   ├── pyproject.toml              # Dependencies: mcp, qdrant-client, httpx
│   ├── __init__.py                 # Empty
│   ├── config.py                   # Env var config with defaults
│   ├── server.py                   # FastMCP entrypoint, tool registration, stdio/SSE
│   ├── namespaces.py               # SQLite CRUD for namespace registry
│   ├── embeddings.py               # Ollama HTTP client for generating embeddings
│   ├── schema.py                   # Payload validation against namespace_fields
│   ├── storage.py                  # Store/delete/get/list Qdrant entries
│   └── search.py                   # Semantic search + dual-query context merge
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Shared fixtures (in-memory SQLite, mock Qdrant)
│   ├── test_namespaces.py          # Namespace registry unit tests
│   ├── test_schema.py              # Schema validation unit tests
│   ├── test_embeddings.py          # Embedding client unit tests
│   ├── test_storage.py             # Storage operations unit tests
│   └── test_search.py              # Search + dual-query unit tests
└── data/                           # Gitignored, created at runtime
    ├── qdrant/
    ├── sqlite/
    └── ollama/
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `mcp_server/pyproject.toml`
- Create: `mcp_server/Dockerfile`
- Create: `mcp_server/__init__.py`
- Create: `mcp_server/config.py`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
# mcp_server/pyproject.toml
[project]
name = "vector-db-mcp-server"
version = "0.1.0"
description = "Local vector DB MCP server for RAG with Claude"
requires-python = ">=3.12"
dependencies = [
    "mcp[cli]>=1.26.0",
    "qdrant-client>=1.17.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
# mcp_server/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 11488

ENTRYPOINT ["python", "server.py"]
CMD ["--sse"]
```

- [ ] **Step 3: Create config.py**

```python
# mcp_server/config.py
import os


QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "768"))
MCP_SSE_PORT = int(os.environ.get("MCP_SSE_PORT", "11488"))
SQLITE_PATH = os.environ.get("SQLITE_PATH", "/app/data/sqlite/namespaces.db")
```

- [ ] **Step 4: Create docker-compose.yml**

```yaml
# docker-compose.yml
services:
  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - ./data/qdrant:/qdrant/storage
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ./data/ollama:/root/.ollama
    restart: unless-stopped
    entrypoint: >
      sh -c "ollama serve &
             sleep 5 &&
             ollama pull nomic-embed-text &&
             wait"

  mcp-server:
    build:
      context: ./mcp_server
    container_name: vector-db-mcp-server
    environment:
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - OLLAMA_HOST=ollama
      - OLLAMA_PORT=11434
      - EMBEDDING_MODEL=${EMBEDDING_MODEL:-nomic-embed-text}
      - EMBEDDING_DIMENSIONS=${EMBEDDING_DIMENSIONS:-768}
      - MCP_SSE_PORT=${MCP_SSE_PORT:-11488}
      - SQLITE_PATH=/app/data/sqlite/namespaces.db
    ports:
      - "${MCP_SSE_PORT:-11488}:11488"
    volumes:
      - ./data/sqlite:/app/data/sqlite
    depends_on:
      - qdrant
      - ollama
    restart: unless-stopped
```

- [ ] **Step 5: Create .env.example and .gitignore**

`.env.example`:
```env
MCP_SSE_PORT=11488
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSIONS=768
```

`.gitignore`:
```
data/
__pycache__/
*.pyc
.env
*.egg-info/
.pytest_cache/
```

- [ ] **Step 6: Create empty __init__.py files and conftest.py**

`mcp_server/__init__.py`: empty file

`tests/__init__.py`: empty file

```python
# tests/conftest.py
import sqlite3
import pytest
from mcp_server.namespaces import NamespaceRegistry


@pytest.fixture
def db():
    """In-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    registry = NamespaceRegistry(conn)
    registry.initialize()
    yield conn
    conn.close()


@pytest.fixture
def registry(db):
    """Namespace registry backed by in-memory SQLite."""
    return NamespaceRegistry(db)
```

- [ ] **Step 7: Commit**

```bash
git add mcp_server/pyproject.toml mcp_server/Dockerfile mcp_server/__init__.py \
        mcp_server/config.py docker-compose.yml .env.example .gitignore \
        tests/__init__.py tests/conftest.py
git commit -m "feat: project scaffolding with Docker Compose, config, and test fixtures"
```

---

### Task 2: SQLite Namespace Registry (TDD)

**Files:**
- Create: `tests/test_namespaces.py`
- Create: `mcp_server/namespaces.py`

- [ ] **Step 1: Write failing tests for namespace CRUD**

```python
# tests/test_namespaces.py
import pytest
from mcp_server.namespaces import NamespaceRegistry


def test_create_namespace(registry):
    ns = registry.create(
        name="mtg-cards",
        description="Magic: The Gathering card collection",
        embedding_instructions="$card_name. $type_line. $original_text",
        summary_instructions=None,
        include_context=True,
        fields=[
            {"field_name": "card_name", "field_type": "string", "required": True,
             "description": "Card name", "filterable": True},
            {"field_name": "colors", "field_type": "string[]", "required": True,
             "description": "Color identity", "filterable": True},
        ],
    )
    assert ns["name"] == "mtg-cards"
    assert ns["qdrant_collection"] == "mtg-cards"
    assert ns["status"] == "proposed"
    assert len(ns["fields"]) == 2


def test_create_duplicate_namespace_raises(registry):
    registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])
    with pytest.raises(ValueError, match="already exists"):
        registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])


def test_list_namespaces(registry):
    registry.create(name="ns1", description="first", embedding_instructions="$original_text", fields=[])
    registry.create(name="ns2", description="second", embedding_instructions="$original_text", fields=[])
    result = registry.list_all()
    assert len(result) == 2
    names = [ns["name"] for ns in result]
    assert "ns1" in names
    assert "ns2" in names


def test_get_namespace(registry):
    registry.create(name="test", description="desc", embedding_instructions="$original_text", fields=[])
    ns = registry.get("test")
    assert ns is not None
    assert ns["name"] == "test"
    assert ns["description"] == "desc"


def test_get_nonexistent_namespace_returns_none(registry):
    assert registry.get("nonexistent") is None


def test_confirm_namespace(registry):
    registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])
    ns = registry.confirm("test")
    assert ns["status"] == "active"


def test_confirm_nonexistent_raises(registry):
    with pytest.raises(ValueError, match="not found"):
        registry.confirm("nonexistent")


def test_confirm_already_active_raises(registry):
    registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])
    registry.confirm("test")
    with pytest.raises(ValueError, match="not in 'proposed' status"):
        registry.confirm("test")


def test_update_namespace(registry):
    registry.create(name="test", description="old", embedding_instructions="$original_text", fields=[])
    registry.confirm("test")
    ns = registry.update("test", description="new", embedding_instructions="$card_name $original_text")
    assert ns["description"] == "new"
    assert ns["embedding_instructions"] == "$card_name $original_text"


def test_get_namespace_includes_fields(registry):
    registry.create(
        name="test",
        description="",
        embedding_instructions="$original_text",
        fields=[
            {"field_name": "color", "field_type": "string", "required": True,
             "description": "Color", "filterable": True},
        ],
    )
    ns = registry.get("test")
    assert len(ns["fields"]) == 1
    assert ns["fields"][0]["field_name"] == "color"
    assert ns["fields"][0]["required"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp_server && pip install -e ".[dev]" && cd .. && python -m pytest tests/test_namespaces.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.namespaces'`

- [ ] **Step 3: Implement namespaces.py**

```python
# mcp_server/namespaces.py
import sqlite3
import uuid
from datetime import datetime, timezone


class NamespaceRegistry:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def initialize(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS namespaces (
                id                    TEXT PRIMARY KEY,
                name                  TEXT UNIQUE NOT NULL,
                qdrant_collection     TEXT UNIQUE NOT NULL,
                description           TEXT,
                embedding_instructions TEXT NOT NULL,
                summary_instructions  TEXT,
                include_context       BOOLEAN DEFAULT 1,
                status                TEXT DEFAULT 'proposed',
                created_at            TEXT NOT NULL,
                updated_at            TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS namespace_fields (
                id              TEXT PRIMARY KEY,
                namespace_id    TEXT NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
                field_name      TEXT NOT NULL,
                field_type      TEXT NOT NULL,
                required        BOOLEAN DEFAULT 0,
                description     TEXT,
                filterable      BOOLEAN DEFAULT 1,
                UNIQUE(namespace_id, field_name)
            );
        """)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def create(
        self,
        name: str,
        description: str,
        embedding_instructions: str,
        fields: list[dict],
        summary_instructions: str | None = None,
        include_context: bool = True,
        status: str = "proposed",
    ) -> dict:
        existing = self.conn.execute(
            "SELECT id FROM namespaces WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            raise ValueError(f"Namespace '{name}' already exists")

        ns_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO namespaces
               (id, name, qdrant_collection, description, embedding_instructions,
                summary_instructions, include_context, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ns_id, name, name, description, embedding_instructions,
             summary_instructions, include_context, status, now, now),
        )

        for field in fields:
            self.conn.execute(
                """INSERT INTO namespace_fields
                   (id, namespace_id, field_name, field_type, required, description, filterable)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), ns_id, field["field_name"], field["field_type"],
                 field.get("required", False), field.get("description", ""),
                 field.get("filterable", True)),
            )

        self.conn.commit()
        return self.get(name)

    def list_all(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, name, description, status, created_at, updated_at FROM namespaces"
        ).fetchall()
        return [dict(row) for row in rows]

    def get(self, name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM namespaces WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None

        ns = dict(row)
        fields = self.conn.execute(
            "SELECT * FROM namespace_fields WHERE namespace_id = ?", (ns["id"],)
        ).fetchall()
        ns["fields"] = [dict(f) for f in fields]
        return ns

    def confirm(self, name: str) -> dict:
        ns = self.get(name)
        if ns is None:
            raise ValueError(f"Namespace '{name}' not found")
        if ns["status"] != "proposed":
            raise ValueError(f"Namespace '{name}' is not in 'proposed' status (current: {ns['status']})")

        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE namespaces SET status = 'active', updated_at = ? WHERE name = ?",
            (now, name),
        )
        self.conn.commit()
        return self.get(name)

    def update(self, name: str, **kwargs) -> dict:
        ns = self.get(name)
        if ns is None:
            raise ValueError(f"Namespace '{name}' not found")

        allowed = {"description", "embedding_instructions", "summary_instructions", "include_context"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return ns

        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [name]
        self.conn.execute(f"UPDATE namespaces SET {set_clause} WHERE name = ?", values)
        self.conn.commit()
        return self.get(name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_namespaces.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_namespaces.py mcp_server/namespaces.py
git commit -m "feat: SQLite namespace registry with CRUD operations"
```

---

### Task 3: Schema Validation (TDD)

**Files:**
- Create: `tests/test_schema.py`
- Create: `mcp_server/schema.py`

- [ ] **Step 1: Write failing tests for schema validation**

```python
# tests/test_schema.py
import pytest
from mcp_server.schema import validate_payload, apply_embedding_template


def test_validate_payload_passes_with_all_required_fields():
    fields = [
        {"field_name": "card_name", "field_type": "string", "required": True},
        {"field_name": "colors", "field_type": "string[]", "required": True},
        {"field_name": "tags", "field_type": "string[]", "required": False},
    ]
    payload = {"card_name": "Sheoldred", "colors": ["B"]}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_validate_payload_fails_missing_required_field():
    fields = [
        {"field_name": "card_name", "field_type": "string", "required": True},
        {"field_name": "colors", "field_type": "string[]", "required": True},
    ]
    payload = {"card_name": "Sheoldred"}
    errors = validate_payload(payload, fields)
    assert len(errors) == 1
    assert "colors" in errors[0]


def test_validate_payload_fails_wrong_type_string():
    fields = [
        {"field_name": "card_name", "field_type": "string", "required": True},
    ]
    payload = {"card_name": 123}
    errors = validate_payload(payload, fields)
    assert len(errors) == 1
    assert "string" in errors[0].lower()


def test_validate_payload_fails_wrong_type_string_array():
    fields = [
        {"field_name": "colors", "field_type": "string[]", "required": True},
    ]
    payload = {"colors": "B"}
    errors = validate_payload(payload, fields)
    assert len(errors) == 1


def test_validate_payload_passes_int_type():
    fields = [
        {"field_name": "cmc", "field_type": "int", "required": True},
    ]
    payload = {"cmc": 4}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_validate_payload_passes_float_type():
    fields = [
        {"field_name": "score", "field_type": "float", "required": True},
    ]
    payload = {"score": 3.5}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_validate_payload_passes_bool_type():
    fields = [
        {"field_name": "active", "field_type": "bool", "required": True},
    ]
    payload = {"active": True}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_apply_embedding_template_with_variables():
    template = "$card_name. $type_line. $original_text"
    payload = {"card_name": "Sheoldred", "type_line": "Creature", "original_text": "Deathtouch"}
    result = apply_embedding_template(template, payload)
    assert result == "Sheoldred. Creature. Deathtouch"


def test_apply_embedding_template_without_variables():
    template = "Just embed the original text as-is"
    payload = {"original_text": "Some card text"}
    result = apply_embedding_template(template, payload)
    assert result == "Some card text"


def test_apply_embedding_template_handles_braces_in_values():
    template = "$card_name. $mana_cost. $original_text"
    payload = {
        "card_name": "Sheoldred",
        "mana_cost": "{2}{B}{B}",
        "original_text": "Deathtouch",
    }
    result = apply_embedding_template(template, payload)
    assert result == "Sheoldred. {2}{B}{B}. Deathtouch"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.schema'`

- [ ] **Step 3: Implement schema.py**

```python
# mcp_server/schema.py
from string import Template

TYPE_VALIDATORS = {
    "string": lambda v: isinstance(v, str),
    "string[]": lambda v: isinstance(v, list) and all(isinstance(i, str) for i in v),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
}


def validate_payload(payload: dict, fields: list[dict]) -> list[str]:
    errors = []
    for field in fields:
        name = field["field_name"]
        required = field.get("required", False)
        field_type = field["field_type"]

        if name not in payload:
            if required:
                errors.append(f"Missing required field: {name}")
            continue

        value = payload[name]
        validator = TYPE_VALIDATORS.get(field_type)
        if validator and not validator(value):
            errors.append(f"Field '{name}' expected type {field_type}, got {type(value).__name__}")

    return errors


def apply_embedding_template(template_str: str, payload: dict) -> str:
    if "$" not in template_str:
        return payload.get("original_text", "")

    tmpl = Template(template_str)
    return tmpl.safe_substitute(payload)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_schema.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_schema.py mcp_server/schema.py
git commit -m "feat: payload validation and embedding template engine"
```

---

### Task 4: Ollama Embeddings Client (TDD)

**Files:**
- Create: `tests/test_embeddings.py`
- Create: `mcp_server/embeddings.py`

- [ ] **Step 1: Write failing tests for embedding client**

```python
# tests/test_embeddings.py
import json
import pytest
from unittest.mock import patch, MagicMock
from mcp_server.embeddings import OllamaEmbedder


@pytest.fixture
def embedder():
    return OllamaEmbedder(host="localhost", port=11434, model="nomic-embed-text")


def test_embed_returns_vector(embedder):
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"embedding": [0.1] * 768}

    with patch("httpx.post", return_value=fake_response):
        vector = embedder.embed("hello world")
        assert len(vector) == 768
        assert vector[0] == 0.1


def test_embed_calls_correct_url(embedder):
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"embedding": [0.0] * 768}

    with patch("httpx.post", return_value=fake_response) as mock_post:
        embedder.embed("test")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:11434/api/embed"
        body = call_args[1]["json"]
        assert body["model"] == "nomic-embed-text"
        assert body["input"] == "test"


def test_embed_raises_on_http_error(embedder):
    fake_response = MagicMock()
    fake_response.status_code = 500
    fake_response.text = "Internal Server Error"
    fake_response.raise_for_status.side_effect = Exception("500 Server Error")

    with patch("httpx.post", return_value=fake_response):
        with pytest.raises(Exception, match="500"):
            embedder.embed("test")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_embeddings.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.embeddings'`

- [ ] **Step 3: Implement embeddings.py**

```python
# mcp_server/embeddings.py
import httpx


class OllamaEmbedder:
    def __init__(self, host: str, port: int, model: str):
        self.url = f"http://{host}:{port}/api/embed"
        self.model = model

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            self.url,
            json={"model": self.model, "input": text},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["embedding"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_embeddings.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_embeddings.py mcp_server/embeddings.py
git commit -m "feat: Ollama embedding client with HTTP wrapper"
```

---

### Task 5: Storage Operations (TDD)

**Files:**
- Create: `tests/test_storage.py`
- Create: `mcp_server/storage.py`

- [ ] **Step 1: Write failing tests for storage operations**

```python
# tests/test_storage.py
import pytest
from unittest.mock import MagicMock, patch, call
from mcp_server.storage import StorageManager
from mcp_server.namespaces import NamespaceRegistry


@pytest.fixture
def mock_qdrant():
    client = MagicMock()
    client.collection_exists.return_value = True
    return client


@pytest.fixture
def mock_embedder():
    embedder = MagicMock()
    embedder.embed.return_value = [0.1] * 768
    return embedder


@pytest.fixture
def storage(registry, mock_qdrant, mock_embedder):
    # Create and activate a test namespace
    registry.create(
        name="test-ns",
        description="Test namespace",
        embedding_instructions="$original_text",
        fields=[
            {"field_name": "category", "field_type": "string", "required": True,
             "description": "Category", "filterable": True},
        ],
    )
    registry.confirm("test-ns")
    return StorageManager(registry, mock_qdrant, mock_embedder)


def test_store_entry_returns_id(storage, mock_qdrant):
    entry_id = storage.store(
        namespace="test-ns",
        original_text="Hello world",
        entry_type="note",
        payload={"category": "test"},
    )
    assert entry_id is not None
    assert isinstance(entry_id, str)
    mock_qdrant.upsert.assert_called_once()


def test_store_entry_validates_required_fields(storage):
    with pytest.raises(ValueError, match="category"):
        storage.store(
            namespace="test-ns",
            original_text="Hello",
            entry_type="note",
            payload={},
        )


def test_store_entry_rejects_inactive_namespace(registry, mock_qdrant, mock_embedder):
    registry.create(name="proposed-ns", description="", embedding_instructions="$original_text", fields=[])
    storage = StorageManager(registry, mock_qdrant, mock_embedder)
    with pytest.raises(ValueError, match="not active"):
        storage.store(namespace="proposed-ns", original_text="test", entry_type="note", payload={})


def test_store_entry_applies_embedding_template(storage, mock_embedder):
    storage.store(
        namespace="test-ns",
        original_text="Hello world",
        entry_type="note",
        payload={"category": "test"},
    )
    mock_embedder.embed.assert_called_once_with("Hello world")


def test_store_entry_includes_common_fields_in_payload(storage, mock_qdrant):
    storage.store(
        namespace="test-ns",
        original_text="Hello world",
        entry_type="note",
        payload={"category": "test", "tags": ["a"]},
    )
    upsert_call = mock_qdrant.upsert.call_args
    points = upsert_call[1]["points"]
    p = points[0].payload
    assert p["original_text"] == "Hello world"
    assert p["embedded_text"] == "Hello world"
    assert p["entry_type"] == "note"
    assert p["category"] == "test"
    assert "created_at" in p
    assert "updated_at" in p


def test_delete_entry(storage, mock_qdrant):
    storage.store(
        namespace="test-ns",
        original_text="Hello",
        entry_type="note",
        payload={"category": "test"},
    )
    storage.delete(namespace="test-ns", entry_id="some-uuid")
    mock_qdrant.delete.assert_called_once()


def test_get_entry(storage, mock_qdrant):
    fake_point = MagicMock()
    fake_point.id = "some-uuid"
    fake_point.payload = {"original_text": "Hello", "entry_type": "note"}
    mock_qdrant.retrieve.return_value = [fake_point]

    result = storage.get(namespace="test-ns", entry_id="some-uuid")
    assert result["id"] == "some-uuid"
    assert result["payload"]["original_text"] == "Hello"


def test_get_entry_not_found(storage, mock_qdrant):
    mock_qdrant.retrieve.return_value = []
    result = storage.get(namespace="test-ns", entry_id="missing")
    assert result is None


def test_list_entries(storage, mock_qdrant):
    fake_point = MagicMock()
    fake_point.id = "uuid-1"
    fake_point.payload = {"original_text": "Hello", "entry_type": "note"}
    mock_result = MagicMock()
    mock_result.points = [fake_point]
    mock_result.next_page_offset = None
    mock_qdrant.scroll.return_value = mock_result

    results = storage.list_entries(namespace="test-ns", limit=10)
    assert len(results) == 1
    assert results[0]["id"] == "uuid-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.storage'`

- [ ] **Step 3: Implement storage.py**

```python
# mcp_server/storage.py
import uuid
from datetime import datetime, timezone

from qdrant_client.models import PointStruct, PointIdsList

from mcp_server.namespaces import NamespaceRegistry
from mcp_server.embeddings import OllamaEmbedder
from mcp_server.schema import validate_payload, apply_embedding_template


class StorageManager:
    def __init__(self, registry: NamespaceRegistry, qdrant, embedder: OllamaEmbedder):
        self.registry = registry
        self.qdrant = qdrant
        self.embedder = embedder

    def store(
        self,
        namespace: str,
        original_text: str,
        entry_type: str,
        payload: dict,
    ) -> str:
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")
        if ns["status"] != "active":
            raise ValueError(f"Namespace '{namespace}' is not active (status: {ns['status']})")

        errors = validate_payload(payload, ns["fields"])
        if errors:
            raise ValueError(f"Payload validation failed: {'; '.join(errors)}")

        all_fields = {**payload, "original_text": original_text}
        embedded_text = apply_embedding_template(ns["embedding_instructions"], all_fields)
        vector = self.embedder.embed(embedded_text)

        now = datetime.now(timezone.utc).isoformat()
        entry_id = str(uuid.uuid4())

        full_payload = {
            **payload,
            "original_text": original_text,
            "embedded_text": embedded_text,
            "entry_type": entry_type,
            "source_id": payload.get("source_id"),
            "source_url": payload.get("source_url"),
            "tags": payload.get("tags", []),
            "created_at": now,
            "updated_at": now,
        }

        self.qdrant.upsert(
            collection_name=ns["qdrant_collection"],
            points=[PointStruct(id=entry_id, vector=vector, payload=full_payload)],
        )

        return entry_id

    def delete(self, namespace: str, entry_id: str):
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")

        self.qdrant.delete(
            collection_name=ns["qdrant_collection"],
            points_selector=PointIdsList(points=[entry_id]),
        )

    def get(self, namespace: str, entry_id: str) -> dict | None:
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")

        results = self.qdrant.retrieve(
            collection_name=ns["qdrant_collection"],
            ids=[entry_id],
            with_payload=True,
        )

        if not results:
            return None

        point = results[0]
        return {"id": point.id, "payload": point.payload}

    def list_entries(
        self, namespace: str, limit: int = 20, offset: str | None = None, filters=None
    ) -> list[dict]:
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")

        result = self.qdrant.scroll(
            collection_name=ns["qdrant_collection"],
            limit=limit,
            offset=offset,
            scroll_filter=filters,
            with_payload=True,
        )

        return [{"id": p.id, "payload": p.payload} for p in result.points]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_storage.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_storage.py mcp_server/storage.py
git commit -m "feat: storage operations for Qdrant entries with validation"
```

---

### Task 6: Search with Dual-Query (TDD)

**Files:**
- Create: `tests/test_search.py`
- Create: `mcp_server/search.py`

- [ ] **Step 1: Write failing tests for search and dual-query**

```python
# tests/test_search.py
import pytest
from unittest.mock import MagicMock
from mcp_server.search import SearchManager


@pytest.fixture
def mock_qdrant():
    return MagicMock()


@pytest.fixture
def mock_embedder():
    embedder = MagicMock()
    embedder.embed.return_value = [0.1] * 768
    return embedder


@pytest.fixture
def search_mgr(registry, mock_qdrant, mock_embedder):
    # Active namespace with include_context=True
    registry.create(
        name="test-ns",
        description="Test",
        embedding_instructions="$original_text",
        include_context=True,
        fields=[],
    )
    registry.confirm("test-ns")
    # Context namespace with include_context=False
    registry.create(
        name="context",
        description="Cross-cutting decisions",
        embedding_instructions="$original_text $reasoning",
        include_context=False,
        status="active",
        fields=[
            {"field_name": "related_namespaces", "field_type": "string[]", "required": True,
             "description": "Related namespaces", "filterable": True},
            {"field_name": "decision_type", "field_type": "string", "required": True,
             "description": "Decision type", "filterable": True},
            {"field_name": "reasoning", "field_type": "string", "required": True,
             "description": "Reasoning", "filterable": False},
        ],
    )
    # Manually set status to active since it was created as proposed
    registry.confirm("context")
    return SearchManager(registry, mock_qdrant, mock_embedder)


def _make_scored_point(point_id, score, payload):
    p = MagicMock()
    p.id = point_id
    p.score = score
    p.payload = payload
    return p


def test_search_returns_results(search_mgr, mock_qdrant):
    mock_qdrant.query_points.return_value = MagicMock(
        points=[_make_scored_point("p1", 0.9, {"original_text": "hello"})]
    )
    results = search_mgr.search(namespace="test-ns", query="hello")
    assert len(results) == 1
    assert results[0]["id"] == "p1"
    assert results[0]["score"] == 0.9


def test_search_embeds_query(search_mgr, mock_embedder, mock_qdrant):
    mock_qdrant.query_points.return_value = MagicMock(points=[])
    search_mgr.search(namespace="test-ns", query="find me")
    mock_embedder.embed.assert_called_with("find me")


def test_search_dual_queries_context(search_mgr, mock_qdrant):
    domain_point = _make_scored_point("p1", 0.9, {"original_text": "domain result"})
    context_point = _make_scored_point("p2", 0.85, {"original_text": "context result",
                                                      "related_namespaces": ["test-ns"]})

    mock_qdrant.query_points.side_effect = [
        MagicMock(points=[domain_point]),   # domain query
        MagicMock(points=[context_point]),  # context query
    ]

    results = search_mgr.search(namespace="test-ns", query="test")
    assert mock_qdrant.query_points.call_count == 2
    assert len(results) == 2
    assert results[0]["id"] == "p1"  # higher score first
    assert results[1]["id"] == "p2"


def test_search_skips_context_when_disabled(registry, mock_qdrant, mock_embedder):
    registry.create(
        name="no-context-ns",
        description="",
        embedding_instructions="$original_text",
        include_context=False,
        fields=[],
    )
    registry.confirm("no-context-ns")
    search_mgr = SearchManager(registry, mock_qdrant, mock_embedder)

    mock_qdrant.query_points.return_value = MagicMock(points=[])
    search_mgr.search(namespace="no-context-ns", query="test")
    assert mock_qdrant.query_points.call_count == 1  # only domain, no context


def test_search_merges_and_sorts_by_score(search_mgr, mock_qdrant):
    p1 = _make_scored_point("p1", 0.7, {"original_text": "low score domain"})
    p2 = _make_scored_point("p2", 0.95, {"original_text": "high score context",
                                          "related_namespaces": ["test-ns"]})

    mock_qdrant.query_points.side_effect = [
        MagicMock(points=[p1]),
        MagicMock(points=[p2]),
    ]

    results = search_mgr.search(namespace="test-ns", query="test")
    assert results[0]["id"] == "p2"  # context result ranked higher
    assert results[1]["id"] == "p1"


def test_search_nonexistent_namespace_raises(search_mgr):
    with pytest.raises(ValueError, match="not found"):
        search_mgr.search(namespace="nope", query="test")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_server.search'`

- [ ] **Step 3: Implement search.py**

```python
# mcp_server/search.py
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from mcp_server.namespaces import NamespaceRegistry
from mcp_server.embeddings import OllamaEmbedder


class SearchManager:
    def __init__(self, registry: NamespaceRegistry, qdrant, embedder: OllamaEmbedder):
        self.registry = registry
        self.qdrant = qdrant
        self.embedder = embedder

    def search(
        self,
        namespace: str,
        query: str,
        filters: Filter | None = None,
        limit: int = 10,
    ) -> list[dict]:
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")

        query_vector = self.embedder.embed(query)

        # Search the target namespace
        domain_results = self.qdrant.query_points(
            collection_name=ns["qdrant_collection"],
            query=query_vector,
            query_filter=filters,
            limit=limit,
            with_payload=True,
        )

        all_results = [
            {"id": p.id, "score": p.score, "payload": p.payload, "source": namespace}
            for p in domain_results.points
        ]

        # Dual-query the context collection if enabled
        if ns["include_context"]:
            context_ns = self.registry.get("context")
            if context_ns and context_ns["status"] == "active":
                context_filter = Filter(
                    should=[
                        FieldCondition(
                            key="related_namespaces",
                            match=MatchValue(value=namespace),
                        ),
                        FieldCondition(
                            key="related_namespaces",
                            match=MatchValue(value="*"),
                        ),
                    ]
                )
                context_results = self.qdrant.query_points(
                    collection_name=context_ns["qdrant_collection"],
                    query=query_vector,
                    query_filter=context_filter,
                    limit=limit,
                    with_payload=True,
                )
                all_results.extend(
                    {"id": p.id, "score": p.score, "payload": p.payload, "source": "context"}
                    for p in context_results.points
                )

        # Sort by score descending, deduplicate by id
        seen = set()
        deduped = []
        for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
            if r["id"] not in seen:
                seen.add(r["id"])
                deduped.append(r)

        return deduped[:limit]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_search.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_search.py mcp_server/search.py
git commit -m "feat: semantic search with automatic context dual-query"
```

---

### Task 7: MCP Server and Tool Registration

**Files:**
- Create: `mcp_server/server.py`

- [ ] **Step 1: Implement server.py with all MCP tools**

```python
# mcp_server/server.py
import sys
import json
import sqlite3
import os

from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

from mcp_server.config import (
    QDRANT_HOST, QDRANT_PORT, OLLAMA_HOST, OLLAMA_PORT,
    EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, MCP_SSE_PORT, SQLITE_PATH,
)
from mcp_server.namespaces import NamespaceRegistry
from mcp_server.embeddings import OllamaEmbedder
from mcp_server.storage import StorageManager
from mcp_server.search import SearchManager

mcp = FastMCP("vector-db")

# --- Globals initialized in init_services() ---
registry: NamespaceRegistry = None
storage: StorageManager = None
search_mgr: SearchManager = None
qdrant: QdrantClient = None

FIELD_TYPE_TO_QDRANT_INDEX = {
    "string": PayloadSchemaType.KEYWORD,
    "string[]": PayloadSchemaType.KEYWORD,
    "int": PayloadSchemaType.INTEGER,
    "float": PayloadSchemaType.FLOAT,
    "bool": PayloadSchemaType.BOOL,
}


def init_services():
    global registry, storage, search_mgr, qdrant

    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    registry = NamespaceRegistry(conn)
    registry.initialize()

    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    embedder = OllamaEmbedder(host=OLLAMA_HOST, port=OLLAMA_PORT, model=EMBEDDING_MODEL)

    storage = StorageManager(registry, qdrant, embedder)
    search_mgr = SearchManager(registry, qdrant, embedder)

    bootstrap_context_namespace()


def bootstrap_context_namespace():
    existing = registry.get("context")
    if existing is not None:
        return

    registry.create(
        name="context",
        description="Cross-cutting decision knowledge. Auto-queried alongside domain searches.",
        embedding_instructions="$original_text. Reasoning: $reasoning",
        include_context=False,
        status="active",
        fields=[
            {"field_name": "related_namespaces", "field_type": "string[]", "required": True,
             "description": "Namespaces this decision applies to. Use ['*'] for universal.", "filterable": True},
            {"field_name": "decision_type", "field_type": "string", "required": True,
             "description": "Category: direction_change, preference, pattern, constraint", "filterable": True},
            {"field_name": "reasoning", "field_type": "string", "required": True,
             "description": "Why this decision was made", "filterable": False},
        ],
    )

    if not qdrant.collection_exists("context"):
        qdrant.create_collection(
            collection_name="context",
            vectors_config=VectorParams(size=EMBEDDING_DIMENSIONS, distance=Distance.COSINE),
        )
        qdrant.create_payload_index("context", "related_namespaces", PayloadSchemaType.KEYWORD)
        qdrant.create_payload_index("context", "decision_type", PayloadSchemaType.KEYWORD)
        qdrant.create_payload_index("context", "entry_type", PayloadSchemaType.KEYWORD)
        qdrant.create_payload_index("context", "tags", PayloadSchemaType.KEYWORD)


# --- Namespace Management Tools ---

@mcp.tool()
def list_namespaces() -> str:
    """List all namespaces with their name, description, and status."""
    namespaces = registry.list_all()
    return json.dumps(namespaces, indent=2)


@mcp.tool()
def get_namespace_config(namespace: str) -> str:
    """Get full configuration for a namespace including schema and embedding instructions."""
    ns = registry.get(namespace)
    if ns is None:
        return json.dumps({"error": f"Namespace '{namespace}' not found"})
    return json.dumps(ns, indent=2)


@mcp.tool()
def propose_namespace(
    name: str,
    description: str,
    embedding_instructions: str,
    fields: str,
    summary_instructions: str = "",
    include_context: bool = True,
) -> str:
    """Propose a new namespace. Fields should be a JSON array of objects with
    field_name, field_type (string|string[]|int|float|bool), required (bool),
    description (str), and filterable (bool). Returns the proposed config for user review."""
    try:
        parsed_fields = json.loads(fields)
        ns = registry.create(
            name=name,
            description=description,
            embedding_instructions=embedding_instructions,
            summary_instructions=summary_instructions or None,
            include_context=include_context,
            fields=parsed_fields,
        )
        return json.dumps({"status": "proposed", "config": ns}, indent=2)
    except (ValueError, json.JSONDecodeError) as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def confirm_namespace(namespace: str) -> str:
    """Confirm a proposed namespace, creating its Qdrant collection and activating it."""
    try:
        ns = registry.confirm(namespace)

        if not qdrant.collection_exists(ns["qdrant_collection"]):
            qdrant.create_collection(
                collection_name=ns["qdrant_collection"],
                vectors_config=VectorParams(size=EMBEDDING_DIMENSIONS, distance=Distance.COSINE),
            )
            # Create payload indexes for filterable fields
            for field in ns["fields"]:
                if field["filterable"]:
                    idx_type = FIELD_TYPE_TO_QDRANT_INDEX.get(field["field_type"])
                    if idx_type:
                        qdrant.create_payload_index(
                            ns["qdrant_collection"], field["field_name"], idx_type
                        )
            # Common field indexes
            qdrant.create_payload_index(ns["qdrant_collection"], "entry_type", PayloadSchemaType.KEYWORD)
            qdrant.create_payload_index(ns["qdrant_collection"], "tags", PayloadSchemaType.KEYWORD)
            qdrant.create_payload_index(ns["qdrant_collection"], "source_id", PayloadSchemaType.KEYWORD)

        return json.dumps({"status": "active", "namespace": ns["name"]})
    except ValueError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def update_namespace_config(
    namespace: str,
    description: str = "",
    embedding_instructions: str = "",
    summary_instructions: str = "",
    include_context: bool | None = None,
) -> str:
    """Update an existing namespace's configuration. Only provided fields are updated."""
    try:
        kwargs = {}
        if description:
            kwargs["description"] = description
        if embedding_instructions:
            kwargs["embedding_instructions"] = embedding_instructions
        if summary_instructions:
            kwargs["summary_instructions"] = summary_instructions
        if include_context is not None:
            kwargs["include_context"] = include_context

        ns = registry.update(namespace, **kwargs)
        return json.dumps({"status": "updated", "config": ns}, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})


# --- Data Operation Tools ---

@mcp.tool()
def store_entry(
    namespace: str,
    original_text: str,
    entry_type: str,
    payload: str,
) -> str:
    """Store a new entry in a namespace. Payload should be a JSON object with
    namespace-specific fields (check get_namespace_config for required fields).
    The server validates the payload, applies embedding instructions, generates
    the embedding via Ollama, and stores in Qdrant."""
    try:
        parsed_payload = json.loads(payload)
        entry_id = storage.store(
            namespace=namespace,
            original_text=original_text,
            entry_type=entry_type,
            payload=parsed_payload,
        )
        return json.dumps({"status": "stored", "entry_id": entry_id})
    except (ValueError, json.JSONDecodeError) as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def search_entries(
    namespace: str,
    query: str,
    limit: int = 10,
) -> str:
    """Semantic search within a namespace. If the namespace has include_context
    enabled, also searches the context collection for relevant decisions and
    merges results ranked by similarity score."""
    try:
        results = search_mgr.search(
            namespace=namespace,
            query=query,
            limit=limit,
        )
        return json.dumps(results, indent=2, default=str)
    except ValueError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_entry(namespace: str, entry_id: str) -> str:
    """Retrieve a specific entry by its ID."""
    try:
        result = storage.get(namespace=namespace, entry_id=entry_id)
        if result is None:
            return json.dumps({"error": f"Entry '{entry_id}' not found"})
        return json.dumps(result, indent=2, default=str)
    except ValueError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def delete_entry(namespace: str, entry_id: str) -> str:
    """Delete a specific entry by its ID."""
    try:
        storage.delete(namespace=namespace, entry_id=entry_id)
        return json.dumps({"status": "deleted", "entry_id": entry_id})
    except ValueError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def list_entries(namespace: str, limit: int = 20) -> str:
    """List entries in a namespace with optional pagination. No semantic search,
    just browsing."""
    try:
        results = storage.list_entries(namespace=namespace, limit=limit)
        return json.dumps(results, indent=2, default=str)
    except ValueError as e:
        return json.dumps({"error": str(e)})


# --- Maintenance Tools ---

@mcp.tool()
def namespace_stats(namespace: str) -> str:
    """Get statistics for a namespace: entry count, embedding model, config summary."""
    try:
        ns = registry.get(namespace)
        if ns is None:
            return json.dumps({"error": f"Namespace '{namespace}' not found"})

        collection_info = qdrant.get_collection(ns["qdrant_collection"])
        return json.dumps({
            "namespace": ns["name"],
            "status": ns["status"],
            "description": ns["description"],
            "points_count": collection_info.points_count,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
            "include_context": bool(ns["include_context"]),
            "field_count": len(ns["fields"]),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def reindex_namespace(namespace: str) -> str:
    """Re-generate embeddings for all entries in a namespace using current
    embedding instructions and model. Use after changing embedding instructions
    or switching models."""
    try:
        ns = registry.get(namespace)
        if ns is None:
            return json.dumps({"error": f"Namespace '{namespace}' not found"})

        embedder = OllamaEmbedder(host=OLLAMA_HOST, port=OLLAMA_PORT, model=EMBEDDING_MODEL)
        collection = ns["qdrant_collection"]

        offset = None
        reindexed = 0
        while True:
            result = qdrant.scroll(
                collection_name=collection,
                limit=50,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if not result.points:
                break

            from mcp_server.schema import apply_embedding_template
            from qdrant_client.models import PointStruct

            points = []
            for point in result.points:
                payload = point.payload
                embedded_text = apply_embedding_template(ns["embedding_instructions"], payload)
                vector = embedder.embed(embedded_text)
                payload["embedded_text"] = embedded_text
                points.append(PointStruct(id=point.id, vector=vector, payload=payload))

            qdrant.upsert(collection_name=collection, points=points)
            reindexed += len(points)

            offset = result.next_page_offset
            if offset is None:
                break

        return json.dumps({"status": "reindexed", "namespace": namespace, "entries": reindexed})
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- Entrypoint ---

def main():
    init_services()

    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", host="0.0.0.0", port=MCP_SSE_PORT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all unit tests to verify nothing is broken**

Run: `python -m pytest tests/ -v`
Expected: All tests from Tasks 2-6 still PASS

- [ ] **Step 3: Commit**

```bash
git add mcp_server/server.py
git commit -m "feat: MCP server with all tools — namespace, storage, search, maintenance"
```

---

### Task 8: Docker Integration Test

**Files:**
- No new files — manual verification

- [ ] **Step 1: Build and start the stack**

```bash
docker compose build
docker compose up -d
```

Expected: All three containers start. Check logs:
```bash
docker compose logs mcp-server
docker compose logs ollama
docker compose logs qdrant
```

- [ ] **Step 2: Wait for Ollama to pull the model**

```bash
docker compose logs -f ollama
```

Expected: Ollama downloads `nomic-embed-text` (~274MB). Wait until you see the model pull complete.

- [ ] **Step 3: Test MCP server via stdio**

```bash
docker exec -i vector-db-mcp-server python server.py --stdio <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}
EOF
```

Expected: JSON response with server capabilities.

- [ ] **Step 4: Test SSE endpoint is accessible**

```bash
curl -s http://localhost:11488/sse
```

Expected: SSE connection opens (or returns an SSE-formatted response).

- [ ] **Step 5: Verify context namespace was bootstrapped**

```bash
docker exec vector-db-mcp-server python -c "
import sqlite3
conn = sqlite3.connect('/app/data/sqlite/namespaces.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT name, status FROM namespaces').fetchall()
for r in rows:
    print(f'{r[\"name\"]}: {r[\"status\"]}')
"
```

Expected output:
```
context: active
```

- [ ] **Step 6: Commit any fixes from integration testing**

```bash
git add -A
git commit -m "fix: integration testing adjustments"
```

---

### Task 9: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

```markdown
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

## Development

```bash
cd mcp_server
pip install -e ".[dev]"
pytest ../tests/ -v
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with setup, usage, and architecture overview"
```

---

### Task 10: Final Spec Update and Commit

**Files:**
- Modify: `docs/superpowers/specs/2026-03-28-local-vector-db-mcp-service-design.md`

- [ ] **Step 1: Update spec to reflect template change**

The spec was already updated to use `string.Template` with `$var` syntax. Commit any remaining spec changes.

```bash
git add docs/
git commit -m "docs: finalize spec and plan"
```

- [ ] **Step 2: Run full test suite one final time**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Final commit with all files**

```bash
git status
# Verify no uncommitted changes remain
```
