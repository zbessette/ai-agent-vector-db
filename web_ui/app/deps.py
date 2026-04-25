import os
import sqlite3
from functools import lru_cache

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


def _open_registry() -> NamespaceRegistry:
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    registry = NamespaceRegistry(conn)
    registry.initialize()
    return registry


def get_qdrant() -> QdrantClient:
    return _qdrant_client()


def get_embedder() -> OllamaEmbedder:
    return _embedder()


def get_registry() -> NamespaceRegistry:
    # Each request gets its own SQLite connection (sqlite3 is not thread-safe across requests)
    return _open_registry()


def get_storage() -> StorageManager:
    return StorageManager(get_registry(), _qdrant_client(), _embedder())


def get_search() -> SearchManager:
    return SearchManager(get_registry(), _qdrant_client(), _embedder())
