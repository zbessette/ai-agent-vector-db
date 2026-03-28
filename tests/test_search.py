import pytest
from unittest.mock import MagicMock
from mcp_server.search import SearchManager


@pytest.fixture
def mock_qdrant():
    return MagicMock()


@pytest.fixture
def mock_embedder():
    embedder = MagicMock()
    embedder.embed.return_value = [0.1] * 768
    return embedder


@pytest.fixture
def search_mgr(registry, mock_qdrant, mock_embedder):
    # Active namespace with include_context=True
    registry.create(
        name="test-ns",
        description="Test",
        embedding_instructions="$original_text",
        include_context=True,
        fields=[],
    )
    registry.confirm("test-ns")
    # Context namespace with include_context=False
    registry.create(
        name="context",
        description="Cross-cutting decisions",
        embedding_instructions="$original_text $reasoning",
        include_context=False,
        fields=[
            {"field_name": "related_namespaces", "field_type": "string[]", "required": True,
             "description": "Related namespaces", "filterable": True},
            {"field_name": "decision_type", "field_type": "string", "required": True,
             "description": "Decision type", "filterable": True},
            {"field_name": "reasoning", "field_type": "string", "required": True,
             "description": "Reasoning", "filterable": False},
        ],
    )
    registry.confirm("context")
    return SearchManager(registry, mock_qdrant, mock_embedder)


def _make_scored_point(point_id, score, payload):
    p = MagicMock()
    p.id = point_id
    p.score = score
    p.payload = payload
    return p


def test_search_returns_results(search_mgr, mock_qdrant):
    mock_qdrant.query_points.return_value = MagicMock(
        points=[_make_scored_point("p1", 0.9, {"original_text": "hello"})]
    )
    results = search_mgr.search(namespace="test-ns", query="hello")
    assert len(results) == 1
    assert results[0]["id"] == "p1"
    assert results[0]["score"] == 0.9


def test_search_embeds_query(search_mgr, mock_embedder, mock_qdrant):
    mock_qdrant.query_points.return_value = MagicMock(points=[])
    search_mgr.search(namespace="test-ns", query="find me")
    mock_embedder.embed.assert_called_with("find me")


def test_search_dual_queries_context(search_mgr, mock_qdrant):
    domain_point = _make_scored_point("p1", 0.9, {"original_text": "domain result"})
    context_point = _make_scored_point("p2", 0.85, {"original_text": "context result",
                                                      "related_namespaces": ["test-ns"]})

    mock_qdrant.query_points.side_effect = [
        MagicMock(points=[domain_point]),   # domain query
        MagicMock(points=[context_point]),  # context query
    ]

    results = search_mgr.search(namespace="test-ns", query="test")
    assert mock_qdrant.query_points.call_count == 2
    assert len(results) == 2
    assert results[0]["id"] == "p1"  # higher score first
    assert results[1]["id"] == "p2"


def test_search_skips_context_when_disabled(registry, mock_qdrant, mock_embedder):
    registry.create(
        name="no-context-ns",
        description="",
        embedding_instructions="$original_text",
        include_context=False,
        fields=[],
    )
    registry.confirm("no-context-ns")
    search_mgr = SearchManager(registry, mock_qdrant, mock_embedder)

    mock_qdrant.query_points.return_value = MagicMock(points=[])
    search_mgr.search(namespace="no-context-ns", query="test")
    assert mock_qdrant.query_points.call_count == 1  # only domain, no context


def test_search_merges_and_sorts_by_score(search_mgr, mock_qdrant):
    p1 = _make_scored_point("p1", 0.7, {"original_text": "low score domain"})
    p2 = _make_scored_point("p2", 0.95, {"original_text": "high score context",
                                          "related_namespaces": ["test-ns"]})

    mock_qdrant.query_points.side_effect = [
        MagicMock(points=[p1]),
        MagicMock(points=[p2]),
    ]

    results = search_mgr.search(namespace="test-ns", query="test")
    assert results[0]["id"] == "p2"  # context result ranked higher
    assert results[1]["id"] == "p1"


def test_search_nonexistent_namespace_raises(search_mgr):
    with pytest.raises(ValueError, match="not found"):
        search_mgr.search(namespace="nope", query="test")
