from unittest.mock import MagicMock

from mcp_server.qdrant_collections import ensure_namespace_collection


def _ns(name="alpha", fields=None):
    return {
        "name": name,
        "qdrant_collection": name,
        "fields": fields or [],
    }


def test_creates_collection_when_missing():
    qdrant = MagicMock()
    qdrant.collection_exists.return_value = False
    ns = _ns(fields=[
        {"field_name": "category", "field_type": "string", "required": True,
         "description": "", "filterable": True},
    ])

    created = ensure_namespace_collection(qdrant, ns, dimensions=768)

    assert created is True
    qdrant.create_collection.assert_called_once()
    # Per-field index for `category` plus 3 common fields
    index_names = [c.args[1] for c in qdrant.create_payload_index.call_args_list]
    assert "category" in index_names
    assert "entry_type" in index_names
    assert "tags" in index_names
    assert "source_id" in index_names


def test_skips_when_collection_already_exists():
    qdrant = MagicMock()
    qdrant.collection_exists.return_value = True
    ns = _ns()

    created = ensure_namespace_collection(qdrant, ns, dimensions=768)

    assert created is False
    qdrant.create_collection.assert_not_called()
    qdrant.create_payload_index.assert_not_called()


def test_skips_non_filterable_fields():
    qdrant = MagicMock()
    qdrant.collection_exists.return_value = False
    ns = _ns(fields=[
        {"field_name": "secret", "field_type": "string", "required": False,
         "description": "", "filterable": False},
    ])

    ensure_namespace_collection(qdrant, ns, dimensions=768)

    index_names = [c.args[1] for c in qdrant.create_payload_index.call_args_list]
    assert "secret" not in index_names


def test_handles_unknown_field_type_gracefully():
    qdrant = MagicMock()
    qdrant.collection_exists.return_value = False
    ns = _ns(fields=[
        {"field_name": "weird", "field_type": "vector", "required": False,
         "description": "", "filterable": True},
    ])

    ensure_namespace_collection(qdrant, ns, dimensions=768)

    index_names = [c.args[1] for c in qdrant.create_payload_index.call_args_list]
    assert "weird" not in index_names  # unknown type → no index
    # Common fields still indexed
    assert "entry_type" in index_names
