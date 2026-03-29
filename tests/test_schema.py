import pytest
from mcp_server.schema import validate_payload, apply_embedding_template


def test_validate_payload_passes_with_all_required_fields():
    fields = [
        {"field_name": "prompt_text", "field_type": "string", "required": True},
        {"field_name": "style", "field_type": "string[]", "required": True},
        {"field_name": "tags", "field_type": "string[]", "required": False},
    ]
    payload = {"prompt_text": "A sunset over mountains", "style": ["photorealistic"]}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_validate_payload_fails_missing_required_field():
    fields = [
        {"field_name": "prompt_text", "field_type": "string", "required": True},
        {"field_name": "style", "field_type": "string[]", "required": True},
    ]
    payload = {"prompt_text": "A sunset over mountains"}
    errors = validate_payload(payload, fields)
    assert len(errors) == 1
    assert "style" in errors[0]


def test_validate_payload_fails_wrong_type_string():
    fields = [
        {"field_name": "prompt_text", "field_type": "string", "required": True},
    ]
    payload = {"prompt_text": 123}
    errors = validate_payload(payload, fields)
    assert len(errors) == 1
    assert "string" in errors[0].lower()


def test_validate_payload_fails_wrong_type_string_array():
    fields = [
        {"field_name": "style", "field_type": "string[]", "required": True},
    ]
    payload = {"style": "photorealistic"}
    errors = validate_payload(payload, fields)
    assert len(errors) == 1


def test_validate_payload_passes_int_type():
    fields = [
        {"field_name": "revision_count", "field_type": "int", "required": True},
    ]
    payload = {"revision_count": 4}
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
        {"field_name": "approved", "field_type": "bool", "required": True},
    ]
    payload = {"approved": True}
    errors = validate_payload(payload, fields)
    assert errors == []


def test_apply_embedding_template_with_variables():
    template = "$prompt_text. $style. $original_text"
    payload = {"prompt_text": "A sunset over mountains", "style": "photorealistic", "original_text": "warm tones, golden hour"}
    result = apply_embedding_template(template, payload)
    assert result == "A sunset over mountains. photorealistic. warm tones, golden hour"


def test_apply_embedding_template_without_variables():
    template = "Just embed the original text as-is"
    payload = {"original_text": "A sunset over mountains with warm lighting"}
    result = apply_embedding_template(template, payload)
    assert result == "A sunset over mountains with warm lighting"


def test_apply_embedding_template_handles_braces_in_values():
    template = "$prompt_text. $aspect_ratio. $original_text"
    payload = {
        "prompt_text": "A sunset over mountains",
        "aspect_ratio": "{16:9}",
        "original_text": "warm tones",
    }
    result = apply_embedding_template(template, payload)
    assert result == "A sunset over mountains. {16:9}. warm tones"
