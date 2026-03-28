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
