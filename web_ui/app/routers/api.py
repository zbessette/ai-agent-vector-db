"""JSON /api/* routes — mirror of the HTML pages, ready for external clients."""
from fastapi import APIRouter, Depends, Response
from fastapi.templating import Jinja2Templates

from mcp_server.namespaces import NamespaceRegistry
from mcp_server.storage import StorageManager
from mcp_server.search import SearchManager

from ..deps import get_registry, get_storage, get_search
from ..errors import AppError
from ..services.search_helpers import filter_by_threshold
from ..services.validation import (
    EntryCreateRequest, EntryUpdateRequest,
    NamespaceCreateRequest, NamespaceUpdateRequest,
    SearchRequest,
)


def register(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/namespaces")
    def list_namespaces(
        status: str | None = None,
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        items = registry.list_all()
        if status:
            items = [n for n in items if n["status"] == status]
        return {"items": items, "total": len(items), "limit": len(items), "offset": 0}

    @router.post("/namespaces", status_code=201)
    def create_namespace(
        body: NamespaceCreateRequest,
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        try:
            ns = registry.create(
                name=body.name,
                description=body.description,
                embedding_instructions=body.embedding_instructions,
                include_context=body.include_context,
                fields=[f.model_dump() for f in body.fields],
            )
        except ValueError as e:
            raise AppError(str(e), status_code=400)
        return ns

    @router.get("/namespaces/{name}")
    def get_namespace(
        name: str,
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        ns = registry.get(name)
        if ns is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)
        return ns

    @router.patch("/namespaces/{name}")
    def update_namespace(
        name: str,
        body: NamespaceUpdateRequest,
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        try:
            return registry.update(name, **body.model_dump(exclude_none=True))
        except ValueError as e:
            raise AppError(str(e), status_code=400)

    @router.post("/namespaces/{name}/confirm")
    def confirm_namespace(
        name: str,
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        try:
            return registry.confirm(name)
        except ValueError as e:
            raise AppError(str(e), status_code=400)

    @router.delete("/namespaces/{name}", status_code=204)
    def delete_namespace(
        name: str,
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        if registry.get(name) is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)
        registry.delete(name)
        return Response(status_code=204)

    @router.get("/namespaces/{name}/entries")
    def list_entries(
        name: str,
        limit: int = 20,
        storage: StorageManager = Depends(get_storage),
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        if registry.get(name) is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)
        # Cursor pagination is a follow-up; v1 returns the first `limit` entries.
        items = storage.list_entries(namespace=name, limit=limit, offset=None)
        return {"items": items, "count": len(items), "limit": limit}

    @router.post("/namespaces/{name}/entries", status_code=201)
    def create_entry(
        name: str,
        body: EntryCreateRequest,
        storage: StorageManager = Depends(get_storage),
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        if registry.get(name) is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)
        try:
            entry_id = storage.store(
                namespace=name,
                original_text=body.original_text,
                entry_type=body.entry_type,
                payload=body.payload,
            )
        except ValueError as e:
            raise AppError(str(e), status_code=400)
        return {"id": entry_id}

    @router.put("/namespaces/{name}/entries/{entry_id}")
    def update_entry(
        name: str,
        entry_id: str,
        body: EntryUpdateRequest,
        storage: StorageManager = Depends(get_storage),
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        if registry.get(name) is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)
        try:
            storage.update(
                namespace=name,
                entry_id=entry_id,
                original_text=body.original_text,
                entry_type=body.entry_type,
                payload=body.payload,
            )
        except ValueError as e:
            raise AppError(str(e), status_code=400)
        return {"id": entry_id}

    @router.delete("/namespaces/{name}/entries/{entry_id}", status_code=204)
    def delete_entry(
        name: str,
        entry_id: str,
        storage: StorageManager = Depends(get_storage),
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        if registry.get(name) is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)
        storage.delete(namespace=name, entry_id=entry_id)
        return Response(status_code=204)

    @router.post("/search")
    def search(
        body: SearchRequest,
        search_mgr: SearchManager = Depends(get_search),
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        if registry.get(body.namespace) is None:
            raise AppError(f"Namespace '{body.namespace}' not found", status_code=404)
        try:
            items = search_mgr.search(
                namespace=body.namespace,
                query=body.query,
                limit=body.top_k,
            )
        except ValueError as e:
            raise AppError(str(e), status_code=400)
        items = filter_by_threshold(items, body.threshold)
        return {"items": items, "total": len(items)}

    return router
