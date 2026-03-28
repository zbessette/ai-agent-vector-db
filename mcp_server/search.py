from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from mcp_server.namespaces import NamespaceRegistry
from mcp_server.embeddings import OllamaEmbedder


class SearchManager:
    def __init__(self, registry: NamespaceRegistry, qdrant, embedder: OllamaEmbedder):
        self.registry = registry
        self.qdrant = qdrant
        self.embedder = embedder

    def search(
        self,
        namespace: str,
        query: str,
        filters: Filter | None = None,
        limit: int = 10,
    ) -> list[dict]:
        ns = self.registry.get(namespace)
        if ns is None:
            raise ValueError(f"Namespace '{namespace}' not found")

        query_vector = self.embedder.embed(query)

        # Search the target namespace
        domain_results = self.qdrant.query_points(
            collection_name=ns["qdrant_collection"],
            query=query_vector,
            query_filter=filters,
            limit=limit,
            with_payload=True,
        )

        all_results = [
            {"id": p.id, "score": p.score, "payload": p.payload, "source": namespace}
            for p in domain_results.points
        ]

        # Dual-query the context collection if enabled
        if ns["include_context"]:
            context_ns = self.registry.get("context")
            if context_ns and context_ns["status"] == "active":
                context_filter = Filter(
                    should=[
                        FieldCondition(
                            key="related_namespaces",
                            match=MatchValue(value=namespace),
                        ),
                        FieldCondition(
                            key="related_namespaces",
                            match=MatchValue(value="*"),
                        ),
                    ]
                )
                context_results = self.qdrant.query_points(
                    collection_name=context_ns["qdrant_collection"],
                    query=query_vector,
                    query_filter=context_filter,
                    limit=limit,
                    with_payload=True,
                )
                all_results.extend(
                    {"id": p.id, "score": p.score, "payload": p.payload, "source": "context"}
                    for p in context_results.points
                )

        # Sort by score descending, deduplicate by id
        seen = set()
        deduped = []
        for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
            if r["id"] not in seen:
                seen.add(r["id"])
                deduped.append(r)

        return deduped[:limit]
