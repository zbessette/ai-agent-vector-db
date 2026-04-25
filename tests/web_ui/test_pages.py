def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_lists_namespaces(client, registry):
    registry.create(
        name="alpha",
        description="alpha ns",
        embedding_instructions="$original_text",
        fields=[],
    )
    registry.confirm("alpha")
    registry.create(
        name="beta",
        description="beta ns",
        embedding_instructions="$original_text",
        fields=[],
    )

    response = client.get("/")
    assert response.status_code == 200
    assert "alpha" in response.text
    assert "beta" in response.text
    assert "Total namespaces" in response.text


def test_namespaces_list_page(client, registry):
    registry.create(
        name="alpha",
        description="alpha ns",
        embedding_instructions="$original_text",
        fields=[],
    )
    response = client.get("/namespaces")
    assert response.status_code == 200
    assert "alpha" in response.text
    assert "New namespace" in response.text


def test_error_page_for_unhandled_path(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404


def test_namespace_detail_renders(client, registry):
    registry.create(
        name="alpha",
        description="alpha description",
        embedding_instructions="$original_text",
        fields=[
            {"field_name": "category", "field_type": "string", "required": True,
             "description": "Category", "filterable": True},
        ],
    )
    registry.confirm("alpha")

    response = client.get("/namespaces/alpha?tab=config")
    assert response.status_code == 200
    assert "alpha" in response.text
    assert "alpha description" in response.text
    assert "category" in response.text  # config tab shows fields
    assert "Entries" in response.text
    assert "Config" in response.text
    assert "Stats" in response.text


def test_namespace_detail_404(client):
    response = client.get("/namespaces/does-not-exist")
    assert response.status_code == 404


def test_entries_partial_returns_rows(client, registry, mock_qdrant):
    from unittest.mock import MagicMock
    registry.create(
        name="alpha",
        description="d",
        embedding_instructions="$original_text",
        fields=[],
    )
    registry.confirm("alpha")

    fake_point = MagicMock()
    fake_point.id = "uuid-1"
    fake_point.payload = {
        "original_text": "Hello world",
        "entry_type": "note",
        "created_at": "2026-04-24T12:00:00+00:00",
    }
    scroll_result = MagicMock()
    scroll_result.points = [fake_point]
    scroll_result.next_page_offset = None
    mock_qdrant.scroll.return_value = scroll_result

    response = client.get("/namespaces/alpha/entries-partial?limit=10")
    assert response.status_code == 200
    assert "uuid-1" in response.text
    assert "Hello world" in response.text
