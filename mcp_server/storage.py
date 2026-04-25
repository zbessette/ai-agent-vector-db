import uuid
from datetime import datetime, timezone

from qdrant_client.models import PointStruct, PointIdsList

try:
    from mcp_server.namespaces import NamespaceRegistry
    from mcp_server.embeddings import OllamaEmbedder
    from mcp_server.schema import validate_payload, apply_embedding_template
except ImportError:
    from namespaces import NamespaceRegistry
    from embeddings import OllamaEmbedder
    from schema import validate_payload, apply_embedding_template


class StorageManager:
    def __init__(self, registry: NamespaceRegistry, qdrant, embedder: OllamaEmbedder):
        self.registry = registry
        self.qdrant = qdrant
        self.embedder = embedder

    def store(
        self,
        namespace: str,
        original_text: str,
        entry_type: str,
        payload: dict,
    ) -> str:
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")
        if ns["status"] != "active":
            raise ValueError(f"Namespace '{namespace}' is not active (status: {ns['status']})")

        errors = validate_payload(payload, ns["fields"])
        if errors:
            raise ValueError(f"Payload validation failed: {'; '.join(errors)}")

        all_fields = {**payload, "original_text": original_text}
        embedded_text = apply_embedding_template(ns["embedding_instructions"], all_fields)
        vector = self.embedder.embed(embedded_text)

        now = datetime.now(timezone.utc).isoformat()
        entry_id = str(uuid.uuid4())

        full_payload = {
            **payload,
            "original_text": original_text,
            "embedded_text": embedded_text,
            "entry_type": entry_type,
            "source_id": payload.get("source_id"),
            "source_url": payload.get("source_url"),
            "tags": payload.get("tags", []),
            "created_at": now,
            "updated_at": now,
        }

        self.qdrant.upsert(
            collection_name=ns["qdrant_collection"],
            points=[PointStruct(id=entry_id, vector=vector, payload=full_payload)],
        )

        return entry_id

    def update(
        self,
        namespace: str,
        entry_id: str,
        original_text: str,
        entry_type: str,
        payload: dict,
    ) -> str:
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")
        if ns["status"] != "active":
            raise ValueError(f"Namespace '{namespace}' is not active (status: {ns['status']})")

        errors = validate_payload(payload, ns["fields"])
        if errors:
            raise ValueError(f"Payload validation failed: {'; '.join(errors)}")

        existing = self.qdrant.retrieve(
            collection_name=ns["qdrant_collection"],
            ids=[entry_id],
            with_payload=True,
        )
        if not existing:
            raise ValueError(f"Entry '{entry_id}' not found in namespace '{namespace}'")

        existing_payload = existing[0].payload or {}
        created_at = existing_payload.get("created_at") or datetime.now(timezone.utc).isoformat()

        all_fields = {**payload, "original_text": original_text}
        embedded_text = apply_embedding_template(ns["embedding_instructions"], all_fields)
        vector = self.embedder.embed(embedded_text)

        now = datetime.now(timezone.utc).isoformat()

        full_payload = {
            **payload,
            "original_text": original_text,
            "embedded_text": embedded_text,
            "entry_type": entry_type,
            "source_id": payload.get("source_id"),
            "source_url": payload.get("source_url"),
            "tags": payload.get("tags", []),
            "created_at": created_at,
            "updated_at": now,
        }

        self.qdrant.upsert(
            collection_name=ns["qdrant_collection"],
            points=[PointStruct(id=entry_id, vector=vector, payload=full_payload)],
        )

        return entry_id

    def delete(self, namespace: str, entry_id: str):
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")

        self.qdrant.delete(
            collection_name=ns["qdrant_collection"],
            points_selector=PointIdsList(points=[entry_id]),
        )

    def get(self, namespace: str, entry_id: str) -> dict | None:
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")

        results = self.qdrant.retrieve(
            collection_name=ns["qdrant_collection"],
            ids=[entry_id],
            with_payload=True,
        )

        if not results:
            return None

        point = results[0]
        return {"id": point.id, "payload": point.payload}

    def list_entries(
        self, namespace: str, limit: int = 20, offset: str | None = None, filters=None
    ) -> list[dict]:
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")

        result = self.qdrant.scroll(
            collection_name=ns["qdrant_collection"],
            limit=limit,
            offset=offset,
            scroll_filter=filters,
            with_payload=True,
        )

        return [{"id": p.id, "payload": p.payload} for p in result.points]
