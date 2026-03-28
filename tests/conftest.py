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
