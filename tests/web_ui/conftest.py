import sqlite3
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from mcp_server.namespaces import NamespaceRegistry
from web_ui.app import deps
from web_ui.app.main import create_app


@pytest.fixture
def registry():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    reg = NamespaceRegistry(conn)
    reg.initialize()
    yield reg
    conn.close()


@pytest.fixture
def mock_qdrant():
    q = MagicMock()
    q.collection_exists.return_value = True

    # Default count: 0 entries per collection
    count_result = MagicMock()
    count_result.count = 0
    q.count.return_value = count_result

    # Default scroll: empty
    scroll_result = MagicMock()
    scroll_result.points = []
    scroll_result.next_page_offset = None
    q.scroll.return_value = scroll_result

    return q


@pytest.fixture
def mock_embedder():
    e = MagicMock()
    e.embed.return_value = [0.1] * 768
    return e


@pytest.fixture
def app(registry, mock_qdrant, mock_embedder):
    app = create_app()
    app.dependency_overrides[deps.get_registry] = lambda: registry
    app.dependency_overrides[deps.get_qdrant] = lambda: mock_qdrant
    app.dependency_overrides[deps.get_embedder] = lambda: mock_embedder
    return app


@pytest.fixture
def client(app):
    return TestClient(app)
