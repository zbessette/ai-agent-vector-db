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
