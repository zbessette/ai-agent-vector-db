from string import Template

TYPE_VALIDATORS = {
    "string": lambda v: isinstance(v, str),
    "string[]": lambda v: isinstance(v, list) and all(isinstance(i, str) for i in v),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
}


def validate_payload(payload: dict, fields: list[dict]) -> list[str]:
    errors = []
    for field in fields:
        name = field["field_name"]
        required = field.get("required", False)
        field_type = field["field_type"]

        if name not in payload:
            if required:
                errors.append(f"Missing required field: {name}")
            continue

        value = payload[name]
        validator = TYPE_VALIDATORS.get(field_type)
        if validator and not validator(value):
            errors.append(f"Field '{name}' expected type {field_type}, got {type(value).__name__}")

    return errors


def apply_embedding_template(template_str: str, payload: dict) -> str:
    if "$" not in template_str:
        return payload.get("original_text", "")

    tmpl = Template(template_str)
    return tmpl.safe_substitute(payload)
