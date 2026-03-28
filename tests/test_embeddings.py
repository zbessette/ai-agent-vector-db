import json
import pytest
from unittest.mock import patch, MagicMock
from mcp_server.embeddings import OllamaEmbedder


@pytest.fixture
def embedder():
    return OllamaEmbedder(host="localhost", port=11434, model="nomic-embed-text")


def test_embed_returns_vector(embedder):
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"embedding": [0.1] * 768}

    with patch("httpx.post", return_value=fake_response):
        vector = embedder.embed("hello world")
        assert len(vector) == 768
        assert vector[0] == 0.1


def test_embed_calls_correct_url(embedder):
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"embedding": [0.0] * 768}

    with patch("httpx.post", return_value=fake_response) as mock_post:
        embedder.embed("test")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:11434/api/embed"
        body = call_args[1]["json"]
        assert body["model"] == "nomic-embed-text"
        assert body["input"] == "test"


def test_embed_raises_on_http_error(embedder):
    fake_response = MagicMock()
    fake_response.status_code = 500
    fake_response.text = "Internal Server Error"
    fake_response.raise_for_status.side_effect = Exception("500 Server Error")

    with patch("httpx.post", return_value=fake_response):
        with pytest.raises(Exception, match="500"):
            embedder.embed("test")
