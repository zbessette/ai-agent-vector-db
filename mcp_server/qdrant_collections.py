"""Qdrant collection/index lifecycle helpers shared by the MCP server and web UI.

A namespace's "physical layer" — the Qdrant collection plus payload indexes —
is created at activation time. Both the MCP `confirm_namespace` tool and the
web UI's `POST /api/namespaces/{name}/confirm` call into the same helper so
the two surfaces stay in sync.
"""
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams


FIELD_TYPE_TO_QDRANT_INDEX = {
    "string": PayloadSchemaType.KEYWORD,
    "string[]": PayloadSchemaType.KEYWORD,
    "int": PayloadSchemaType.INTEGER,
    "float": PayloadSchemaType.FLOAT,
    "bool": PayloadSchemaType.BOOL,
}

# Fields that exist on every entry regardless of namespace schema.
_COMMON_INDEXED_FIELDS = (
    ("entry_type", PayloadSchemaType.KEYWORD),
    ("tags", PayloadSchemaType.KEYWORD),
    ("source_id", PayloadSchemaType.KEYWORD),
)


def ensure_namespace_collection(qdrant, ns: dict, dimensions: int) -> bool:
    """Ensure the Qdrant collection + payload indexes for a namespace exist.

    Idempotent: if the collection already exists, nothing changes.
    Returns True if the collection was created on this call, False otherwise.

    `ns` is a namespace dict from `NamespaceRegistry.get()` — must include
    `qdrant_collection` (str) and `fields` (list of dicts with at least
    `field_name`, `field_type`, `filterable`).
    """
    collection_name = ns["qdrant_collection"]
    if qdrant.collection_exists(collection_name):
        return False

    qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
    )

    # Per-namespace filterable fields
    for field in ns.get("fields", []):
        if not field.get("filterable"):
            continue
        idx_type = FIELD_TYPE_TO_QDRANT_INDEX.get(field["field_type"])
        if idx_type is not None:
            qdrant.create_payload_index(collection_name, field["field_name"], idx_type)

    # Common fields present on every entry
    for name, idx_type in _COMMON_INDEXED_FIELDS:
        qdrant.create_payload_index(collection_name, name, idx_type)

    return True
