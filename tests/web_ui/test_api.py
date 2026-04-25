from unittest.mock import MagicMock


def _setup_namespace(registry, name="alpha"):
    registry.create(
        name=name,
        description="d",
        embedding_instructions="$original_text",
        fields=[
            {"field_name": "category", "field_type": "string", "required": True,
             "description": "Category", "filterable": True},
        ],
    )
    registry.confirm(name)


def test_create_entry_via_api(client, registry, mock_qdrant):
    _setup_namespace(registry)

    response = client.post(
        "/api/namespaces/alpha/entries",
        json={
            "original_text": "hello",
            "entry_type": "note",
            "payload": {"category": "test"},
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    mock_qdrant.upsert.assert_called_once()


def test_create_entry_validation_error(client, registry):
    _setup_namespace(registry)
    response = client.post(
        "/api/namespaces/alpha/entries",
        json={"original_text": "", "entry_type": "note", "payload": {}},
    )
    assert response.status_code == 422


def test_create_entry_namespace_not_found(client):
    response = client.post(
        "/api/namespaces/nope/entries",
        json={"original_text": "hi", "entry_type": "note", "payload": {"category": "x"}},
    )
    assert response.status_code == 404


def test_update_entry_via_api(client, registry, mock_qdrant):
    _setup_namespace(registry)

    fake_existing = MagicMock()
    fake_existing.id = "uuid-1"
    fake_existing.payload = {
        "category": "old",
        "original_text": "old",
        "entry_type": "note",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    mock_qdrant.retrieve.return_value = [fake_existing]

    response = client.put(
        "/api/namespaces/alpha/entries/uuid-1",
        json={"original_text": "new", "entry_type": "note", "payload": {"category": "new"}},
    )
    assert response.status_code == 200
    mock_qdrant.upsert.assert_called_once()


def test_delete_entry_via_api(client, registry, mock_qdrant):
    _setup_namespace(registry)
    response = client.delete("/api/namespaces/alpha/entries/uuid-1")
    assert response.status_code == 204
    mock_qdrant.delete.assert_called_once()


def test_create_namespace_via_api(client):
    response = client.post(
        "/api/namespaces",
        json={
            "name": "newns",
            "description": "d",
            "embedding_instructions": "$original_text",
            "fields": [],
        },
    )
    assert response.status_code == 201
    assert response.json()["name"] == "newns"
    assert response.json()["status"] == "proposed"


def test_create_namespace_invalid_name(client):
    response = client.post(
        "/api/namespaces",
        json={
            "name": "bad name",
            "description": "d",
            "embedding_instructions": "$original_text",
            "fields": [],
        },
    )
    assert response.status_code == 422


def test_confirm_namespace_via_api(client, registry):
    registry.create(name="alpha", description="d", embedding_instructions="$x", fields=[])
    response = client.post("/api/namespaces/alpha/confirm")
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_patch_namespace_via_api(client, registry):
    registry.create(name="alpha", description="old", embedding_instructions="$x", fields=[])
    response = client.patch("/api/namespaces/alpha", json={"description": "new"})
    assert response.status_code == 200
    assert response.json()["description"] == "new"


def test_delete_namespace_via_api(client, registry):
    registry.create(name="alpha", description="d", embedding_instructions="$x", fields=[])
    response = client.delete("/api/namespaces/alpha")
    assert response.status_code == 204
    assert registry.get("alpha") is None


def test_list_entries_pagination_envelope(client, registry, mock_qdrant):
    from unittest.mock import MagicMock
    registry.create(name="alpha", description="d", embedding_instructions="$x", fields=[])
    registry.confirm("alpha")

    fake_point = MagicMock()
    fake_point.id = "u1"
    fake_point.payload = {"original_text": "x", "entry_type": "note", "created_at": "2026-04-24T00:00:00+00:00"}
    mock_qdrant.scroll.return_value = ([fake_point], None)

    response = client.get("/api/namespaces/alpha/entries?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "count" in body
    assert "limit" in body


def test_create_namespace_duplicate_returns_400(client, registry):
    registry.create(name="alpha", description="d", embedding_instructions="$x", fields=[])
    response = client.post(
        "/api/namespaces",
        json={
            "name": "alpha",
            "description": "d2",
            "embedding_instructions": "$x",
            "fields": [],
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json().get("error", "")


def test_reindex_namespace_returns_501(client, registry):
    registry.create(name="alpha", description="d", embedding_instructions="$x", fields=[])
    registry.confirm("alpha")
    response = client.post("/api/namespaces/alpha/reindex")
    assert response.status_code == 501
