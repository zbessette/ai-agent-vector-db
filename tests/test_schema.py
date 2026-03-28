import pytest
from mcp_server.schema import validate_payload, apply_embedding_template


def test_validate_payload_passes_with_all_required_fields():
    fields = [
        {"field_name": "card_name", "field_type": "string", "required": True},
        {"field_name": "colors", "field_type": "string[]", "required": True},
        {"field_name": "tags", "field_type": "string[]", "required": False},
    ]
    payload = {"card_name": "Sheoldred", "colors": ["B"]}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_validate_payload_fails_missing_required_field():
    fields = [
        {"field_name": "card_name", "field_type": "string", "required": True},
        {"field_name": "colors", "field_type": "string[]", "required": True},
    ]
    payload = {"card_name": "Sheoldred"}
    errors = validate_payload(payload, fields)
    assert len(errors) == 1
    assert "colors" in errors[0]


def test_validate_payload_fails_wrong_type_string():
    fields = [
        {"field_name": "card_name", "field_type": "string", "required": True},
    ]
    payload = {"card_name": 123}
    errors = validate_payload(payload, fields)
    assert len(errors) == 1
    assert "string" in errors[0].lower()


def test_validate_payload_fails_wrong_type_string_array():
    fields = [
        {"field_name": "colors", "field_type": "string[]", "required": True},
    ]
    payload = {"colors": "B"}
    errors = validate_payload(payload, fields)
    assert len(errors) == 1


def test_validate_payload_passes_int_type():
    fields = [
        {"field_name": "cmc", "field_type": "int", "required": True},
    ]
    payload = {"cmc": 4}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_validate_payload_passes_float_type():
    fields = [
        {"field_name": "score", "field_type": "float", "required": True},
    ]
    payload = {"score": 3.5}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_validate_payload_passes_bool_type():
    fields = [
        {"field_name": "active", "field_type": "bool", "required": True},
    ]
    payload = {"active": True}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_apply_embedding_template_with_variables():
    template = "$card_name. $type_line. $original_text"
    payload = {"card_name": "Sheoldred", "type_line": "Creature", "original_text": "Deathtouch"}
    result = apply_embedding_template(template, payload)
    assert result == "Sheoldred. Creature. Deathtouch"


def test_apply_embedding_template_without_variables():
    template = "Just embed the original text as-is"
    payload = {"original_text": "Some card text"}
    result = apply_embedding_template(template, payload)
    assert result == "Some card text"


def test_apply_embedding_template_handles_braces_in_values():
    template = "$card_name. $mana_cost. $original_text"
    payload = {
        "card_name": "Sheoldred",
        "mana_cost": "{2}{B}{B}",
        "original_text": "Deathtouch",
    }
    result = apply_embedding_template(template, payload)
    assert result == "Sheoldred. {2}{B}{B}. Deathtouch"
