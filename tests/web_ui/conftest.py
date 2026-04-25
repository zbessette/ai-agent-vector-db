import pytest
from fastapi.testclient import TestClient

from web_ui.app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)
