# mcp_server/server.py
import sys
import json
import sqlite3
import os

from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient

from config import (
    QDRANT_HOST, QDRANT_PORT, OLLAMA_HOST, OLLAMA_PORT,
    EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, MCP_SSE_PORT, SQLITE_PATH,
)
from namespaces import NamespaceRegistry
from embeddings import OllamaEmbedder
from storage import StorageManager
from search import SearchManager

try:
    from mcp_server.qdrant_collections import ensure_namespace_collection
except ImportError:
    from qdrant_collections import ensure_namespace_collection

mcp = FastMCP("vector-db", host="0.0.0.0", port=MCP_SSE_PORT)

# --- Globals initialized in init_services() ---
registry: NamespaceRegistry = None
storage: StorageManager = None
search_mgr: SearchManager = None
qdrant: QdrantClient = None


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

    ns = registry.get("context")
    ensure_namespace_collection(qdrant, ns, EMBEDDING_DIMENSIONS)


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
        ensure_namespace_collection(qdrant, ns, EMBEDDING_DIMENSIONS)
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


@mcp.tool()
def update_proposal(
    namespace: str,
    fields: str = "",
    description: str = "",
    embedding_instructions: str = "",
    summary_instructions: str = "",
    include_context: bool | None = None,
) -> str:
    """Update a proposed namespace before confirmation. Can replace the fields
    list entirely (JSON array) and/or update top-level config. Only works on
    namespaces with status='proposed' — fields cannot be changed once active."""
    try:
        parsed_fields = None
        if fields:
            parsed_fields = json.loads(fields)

        kwargs = {}
        if description:
            kwargs["description"] = description
        if embedding_instructions:
            kwargs["embedding_instructions"] = embedding_instructions
        if summary_instructions:
            kwargs["summary_instructions"] = summary_instructions
        if include_context is not None:
            kwargs["include_context"] = include_context

        ns = registry.update_proposal(namespace, fields=parsed_fields, **kwargs)
        return json.dumps({"status": "updated", "config": ns}, indent=2)
    except (ValueError, json.JSONDecodeError) as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def delete_namespace(namespace: str, confirm: bool = False) -> str:
    """Delete a namespace and all its data. First call without confirm=True to
    see how many entries will be lost. Then call again with confirm=True to
    actually delete. Removes the Qdrant collection (if it exists), namespace
    fields, and the namespace record."""
    try:
        ns = registry.get(namespace)
        if ns is None:
            return json.dumps({"error": f"Namespace '{namespace}' not found"})

        entry_count = 0
        has_collection = False
        if ns["status"] == "active":
            try:
                has_collection = qdrant.collection_exists(ns["qdrant_collection"])
                if has_collection:
                    collection_info = qdrant.get_collection(ns["qdrant_collection"])
                    entry_count = collection_info.points_count
            except Exception:
                pass

        if not confirm:
            return json.dumps({
                "warning": f"This will permanently delete namespace '{namespace}'.",
                "status": ns["status"],
                "entries_to_delete": entry_count,
                "action_required": f"Call delete_namespace again with namespace='{namespace}' and confirm=True to proceed.",
            }, indent=2)

        # Actually delete
        if has_collection:
            qdrant.delete_collection(ns["qdrant_collection"])

        registry.delete(namespace)

        return json.dumps({
            "status": "deleted",
            "namespace": namespace,
            "entries_deleted": entry_count,
        })
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

            from schema import apply_embedding_template
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
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
