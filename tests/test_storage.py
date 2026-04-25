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


def test_update_entry_re_embeds_and_overwrites(storage, mock_qdrant, mock_embedder):
    fake_existing = MagicMock()
    fake_existing.id = "uuid-1"
    fake_existing.payload = {
        "category": "old",
        "original_text": "old text",
        "embedded_text": "old text",
        "entry_type": "note",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    mock_qdrant.retrieve.return_value = [fake_existing]
    mock_embedder.embed.reset_mock()
    mock_qdrant.upsert.reset_mock()

    storage.update(
        namespace="test-ns",
        entry_id="uuid-1",
        original_text="new text",
        entry_type="note",
        payload={"category": "new"},
    )

    # Re-embedded
    mock_embedder.embed.assert_called_once_with("new text")

    # Upserted with same id, preserved created_at, fresh updated_at
    upsert_call = mock_qdrant.upsert.call_args
    points = upsert_call[1]["points"]
    assert len(points) == 1
    p = points[0]
    assert p.id == "uuid-1"
    assert p.payload["original_text"] == "new text"
    assert p.payload["category"] == "new"
    assert p.payload["created_at"] == "2026-01-01T00:00:00+00:00"
    assert p.payload["updated_at"] != "2026-01-01T00:00:00+00:00"


def test_update_entry_validates_payload(storage, mock_qdrant):
    fake_existing = MagicMock()
    fake_existing.id = "uuid-1"
    fake_existing.payload = {"category": "old", "created_at": "x", "updated_at": "x"}
    mock_qdrant.retrieve.return_value = [fake_existing]

    with pytest.raises(ValueError, match="category"):
        storage.update(
            namespace="test-ns",
            entry_id="uuid-1",
            original_text="x",
            entry_type="note",
            payload={},  # missing required category
        )


def test_update_entry_raises_when_missing(storage, mock_qdrant):
    mock_qdrant.retrieve.return_value = []
    with pytest.raises(ValueError, match="not found"):
        storage.update(
            namespace="test-ns",
            entry_id="missing",
            original_text="x",
            entry_type="note",
            payload={"category": "x"},
        )


def test_update_entry_rejects_inactive_namespace(registry, mock_qdrant, mock_embedder):
    registry.create(name="proposed-ns", description="", embedding_instructions="$original_text", fields=[])
    storage = StorageManager(registry, mock_qdrant, mock_embedder)
    with pytest.raises(ValueError, match="not active"):
        storage.update(
            namespace="proposed-ns",
            entry_id="uuid-1",
            original_text="x",
            entry_type="note",
            payload={},
        )
