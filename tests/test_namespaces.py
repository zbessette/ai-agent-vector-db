import pytest
from mcp_server.namespaces import NamespaceRegistry


def test_create_namespace(registry):
    ns = registry.create(
        name="mtg-cards",
        description="Magic: The Gathering card collection",
        embedding_instructions="$card_name. $type_line. $original_text",
        summary_instructions=None,
        include_context=True,
        fields=[
            {"field_name": "card_name", "field_type": "string", "required": True,
             "description": "Card name", "filterable": True},
            {"field_name": "colors", "field_type": "string[]", "required": True,
             "description": "Color identity", "filterable": True},
        ],
    )
    assert ns["name"] == "mtg-cards"
    assert ns["qdrant_collection"] == "mtg-cards"
    assert ns["status"] == "proposed"
    assert len(ns["fields"]) == 2


def test_create_duplicate_namespace_raises(registry):
    registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])
    with pytest.raises(ValueError, match="already exists"):
        registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])


def test_list_namespaces(registry):
    registry.create(name="ns1", description="first", embedding_instructions="$original_text", fields=[])
    registry.create(name="ns2", description="second", embedding_instructions="$original_text", fields=[])
    result = registry.list_all()
    assert len(result) == 2
    names = [ns["name"] for ns in result]
    assert "ns1" in names
    assert "ns2" in names


def test_get_namespace(registry):
    registry.create(name="test", description="desc", embedding_instructions="$original_text", fields=[])
    ns = registry.get("test")
    assert ns is not None
    assert ns["name"] == "test"
    assert ns["description"] == "desc"


def test_get_nonexistent_namespace_returns_none(registry):
    assert registry.get("nonexistent") is None


def test_confirm_namespace(registry):
    registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])
    ns = registry.confirm("test")
    assert ns["status"] == "active"


def test_confirm_nonexistent_raises(registry):
    with pytest.raises(ValueError, match="not found"):
        registry.confirm("nonexistent")


def test_confirm_already_active_raises(registry):
    registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])
    registry.confirm("test")
    with pytest.raises(ValueError, match="not in 'proposed' status"):
        registry.confirm("test")


def test_update_namespace(registry):
    registry.create(name="test", description="old", embedding_instructions="$original_text", fields=[])
    registry.confirm("test")
    ns = registry.update("test", description="new", embedding_instructions="$card_name $original_text")
    assert ns["description"] == "new"
    assert ns["embedding_instructions"] == "$card_name $original_text"


def test_get_namespace_includes_fields(registry):
    registry.create(
        name="test",
        description="",
        embedding_instructions="$original_text",
        fields=[
            {"field_name": "color", "field_type": "string", "required": True,
             "description": "Color", "filterable": True},
        ],
    )
    ns = registry.get("test")
    assert len(ns["fields"]) == 1
    assert ns["fields"][0]["field_name"] == "color"
    assert ns["fields"][0]["required"] is True


# --- update_proposal tests ---


def test_update_proposal_replaces_fields(registry):
    registry.create(
        name="test",
        description="",
        embedding_instructions="$original_text",
        fields=[{"field_name": "old_field", "field_type": "string", "required": True}],
    )
    ns = registry.update_proposal(
        "test",
        fields=[
            {"field_name": "new_field", "field_type": "string", "required": True},
            {"field_name": "another", "field_type": "int", "required": False},
        ],
    )
    assert len(ns["fields"]) == 2
    names = [f["field_name"] for f in ns["fields"]]
    assert "new_field" in names
    assert "another" in names
    assert "old_field" not in names


def test_update_proposal_updates_top_level(registry):
    registry.create(name="test", description="old", embedding_instructions="$original_text", fields=[])
    ns = registry.update_proposal("test", description="new", embedding_instructions="$card_name")
    assert ns["description"] == "new"
    assert ns["embedding_instructions"] == "$card_name"


def test_update_proposal_rejects_active_namespace(registry):
    registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])
    registry.confirm("test")
    with pytest.raises(ValueError, match="status is 'active'"):
        registry.update_proposal("test", fields=[])


def test_update_proposal_nonexistent_raises(registry):
    with pytest.raises(ValueError, match="not found"):
        registry.update_proposal("nonexistent", fields=[])


def test_update_proposal_empty_fields_clears_all(registry):
    registry.create(
        name="test",
        description="",
        embedding_instructions="$original_text",
        fields=[{"field_name": "color", "field_type": "string", "required": True}],
    )
    ns = registry.update_proposal("test", fields=[])
    assert len(ns["fields"]) == 0


def test_update_proposal_fields_none_preserves_existing(registry):
    registry.create(
        name="test",
        description="",
        embedding_instructions="$original_text",
        fields=[{"field_name": "color", "field_type": "string", "required": True}],
    )
    ns = registry.update_proposal("test", description="updated")
    assert len(ns["fields"]) == 1
    assert ns["fields"][0]["field_name"] == "color"
    assert ns["description"] == "updated"


# --- delete tests ---


def test_delete_proposed_namespace(registry):
    registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])
    result = registry.delete("test")
    assert result["name"] == "test"
    assert registry.get("test") is None


def test_delete_active_namespace(registry):
    registry.create(name="test", description="", embedding_instructions="$original_text", fields=[])
    registry.confirm("test")
    result = registry.delete("test")
    assert result["name"] == "test"
    assert result["status"] == "active"
    assert registry.get("test") is None


def test_delete_nonexistent_raises(registry):
    with pytest.raises(ValueError, match="not found"):
        registry.delete("nonexistent")


def test_delete_removes_fields(registry, db):
    registry.create(
        name="test",
        description="",
        embedding_instructions="$original_text",
        fields=[{"field_name": "color", "field_type": "string", "required": True}],
    )
    ns = registry.get("test")
    ns_id = ns["id"]
    registry.delete("test")
    rows = db.execute("SELECT * FROM namespace_fields WHERE namespace_id = ?", (ns_id,)).fetchall()
    assert len(rows) == 0
