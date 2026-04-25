"""FastAPI dependency factories for the web UI.

Service classes are constructed via `Depends(...)` so tests can override individual
backends (qdrant, embedder, registry) and have the override flow through to the
higher-level services that depend on them.
"""
import os
import sqlite3
from functools import lru_cache
from typing import Iterator

from fastapi import Depends
from qdrant_client import QdrantClient

from mcp_server.namespaces import NamespaceRegistry
from mcp_server.embeddings import OllamaEmbedder
from mcp_server.storage import StorageManager
from mcp_server.search import SearchManager

from .config import (
    QDRANT_HOST, QDRANT_PORT, OLLAMA_HOST, OLLAMA_PORT,
    EMBEDDING_MODEL, SQLITE_PATH,
)


@lru_cache(maxsize=1)
def _qdrant_client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


@lru_cache(maxsize=1)
def _embedder() -> OllamaEmbedder:
    return OllamaEmbedder(host=OLLAMA_HOST, port=OLLAMA_PORT, model=EMBEDDING_MODEL)


def get_qdrant() -> QdrantClient:
    return _qdrant_client()


def get_embedder() -> OllamaEmbedder:
    return _embedder()


def get_registry() -> Iterator[NamespaceRegistry]:
    """Yield a request-scoped NamespaceRegistry; close the underlying SQLite connection on cleanup."""
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    registry = NamespaceRegistry(conn)
    registry.initialize()
    try:
        yield registry
    finally:
        conn.close()


def get_storage(
    registry: NamespaceRegistry = Depends(get_registry),
    qdrant: QdrantClient = Depends(get_qdrant),
    embedder: OllamaEmbedder = Depends(get_embedder),
) -> StorageManager:
    return StorageManager(registry, qdrant, embedder)


def get_search(
    registry: NamespaceRegistry = Depends(get_registry),
    qdrant: QdrantClient = Depends(get_qdrant),
    embedder: OllamaEmbedder = Depends(get_embedder),
) -> SearchManager:
    return SearchManager(registry, qdrant, embedder)
