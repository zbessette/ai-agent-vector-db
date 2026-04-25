import logging

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from qdrant_client.http.exceptions import UnexpectedResponse

from mcp_server.namespaces import NamespaceRegistry
from ..deps import get_qdrant, get_registry

logger = logging.getLogger(__name__)


def _namespace_counts(qdrant, namespaces: list[dict]) -> dict[str, int]:
    """Return entry counts per namespace from Qdrant.

    Network / transport errors fall back to 0 so the page still renders;
    anything else (programmer error) propagates so it's caught in tests.
    """
    counts: dict[str, int] = {}
    for ns in namespaces:
        try:
            res = qdrant.count(collection_name=ns["name"], exact=True)
            counts[ns["name"]] = res.count
        except (UnexpectedResponse, httpx.HTTPError, ConnectionError) as exc:
            logger.warning("count failed for namespace '%s': %s", ns["name"], exc)
            counts[ns["name"]] = 0
    return counts


def register(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    def dashboard(
        request: Request,
        registry: NamespaceRegistry = Depends(get_registry),
        qdrant=Depends(get_qdrant),
    ):
        namespaces = registry.list_all()
        counts = _namespace_counts(qdrant, namespaces)
        total_entries = sum(counts.values())
        context_count = counts.get("context", 0)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "namespaces": namespaces,
                "counts": counts,
                "total_namespaces": len(namespaces),
                "total_entries": total_entries,
                "context_count": context_count,
            },
        )

    @router.get("/namespaces")
    def namespaces_list(
        request: Request,
        status: str | None = None,
        registry: NamespaceRegistry = Depends(get_registry),
        qdrant=Depends(get_qdrant),
    ):
        namespaces = registry.list_all()
        if status:
            namespaces = [n for n in namespaces if n["status"] == status]
        counts = _namespace_counts(qdrant, namespaces)
        return templates.TemplateResponse(
            request,
            "namespaces_list.html",
            {
                "namespaces": namespaces,
                "counts": counts,
                "status_filter": status or "",
            },
        )

    return router
