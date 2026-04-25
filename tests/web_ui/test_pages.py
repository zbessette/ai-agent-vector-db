def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_dashboard_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard" in response.text
    assert "Vector DB" in response.text


def test_error_page_for_unhandled_path(client):
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404
