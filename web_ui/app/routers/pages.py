import logging

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from qdrant_client.http.exceptions import UnexpectedResponse

from mcp_server.namespaces import NamespaceRegistry
from ..deps import get_qdrant, get_registry, get_storage, get_search
from ..errors import AppError
from ..services.search_helpers import filter_by_threshold
from ..services.validation import SearchRequest

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

    @router.get("/namespaces/{name}")
    def namespace_detail(
        request: Request,
        name: str,
        tab: str = "entries",
        registry: NamespaceRegistry = Depends(get_registry),
        qdrant=Depends(get_qdrant),
    ):
        ns = registry.get(name)
        if ns is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)

        try:
            count_result = qdrant.count(collection_name=ns["name"], exact=True)
            entry_count = count_result.count
        except (UnexpectedResponse, httpx.HTTPError, ConnectionError) as exc:
            logger.warning("count failed for namespace '%s': %s", ns["name"], exc)
            entry_count = 0

        return templates.TemplateResponse(
            request,
            "namespace_detail.html",
            {
                "ns": ns,
                "tab": tab,
                "entry_count": entry_count,
            },
        )

    @router.get("/namespaces/{name}/entries-partial")
    def entries_partial(
        request: Request,
        name: str,
        limit: int = 20,
        registry: NamespaceRegistry = Depends(get_registry),
        storage=Depends(get_storage),
    ):
        ns = registry.get(name)
        if ns is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)
        # Cursor pagination is a follow-up; v1 returns the first `limit` entries.
        entries = storage.list_entries(namespace=name, limit=limit, offset=None)
        return templates.TemplateResponse(
            request,
            "partials/entries_table.html",
            {"ns": ns, "entries": entries, "limit": limit},
        )

    @router.get("/namespaces/{name}/entries/new")
    def entry_new_form(
        request: Request,
        name: str,
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        ns = registry.get(name)
        if ns is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)
        return templates.TemplateResponse(
            request,
            "partials/entry_form.html",
            {"ns": ns, "entry": None, "errors": {}},
        )

    @router.get("/namespaces/{name}/entries/{entry_id}/edit")
    def entry_edit_form(
        request: Request,
        name: str,
        entry_id: str,
        registry: NamespaceRegistry = Depends(get_registry),
        storage=Depends(get_storage),
    ):
        ns = registry.get(name)
        if ns is None:
            raise AppError(f"Namespace '{name}' not found", status_code=404)
        entry = storage.get(namespace=name, entry_id=entry_id)
        if entry is None:
            raise AppError(f"Entry '{entry_id}' not found", status_code=404)
        return templates.TemplateResponse(
            request,
            "partials/entry_form.html",
            {"ns": ns, "entry": entry, "errors": {}},
        )

    @router.get("/search")
    def search_page(
        request: Request,
        namespace: str | None = None,
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        return templates.TemplateResponse(
            request,
            "search.html",
            {
                "namespaces": registry.list_all(),
                "selected_namespace": namespace or "",
            },
        )

    @router.get("/search/results")
    def search_results(
        request: Request,
        query: str,
        namespace: str,
        top_k: int = 10,
        threshold: float | None = None,
        search_mgr=Depends(get_search),
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        from pydantic import ValidationError
        try:
            req = SearchRequest(query=query, namespace=namespace, top_k=top_k, threshold=threshold)
        except ValidationError as e:
            # Return 400 (not 422) since this is an HTML route, not the JSON API.
            raise AppError(f"Invalid search request: {e.errors()[0]['msg']}", status_code=400)
        if registry.get(req.namespace) is None:
            raise AppError(f"Namespace '{req.namespace}' not found", status_code=404)
        results = search_mgr.search(namespace=req.namespace, query=req.query, limit=req.top_k)
        results = filter_by_threshold(results, req.threshold)
        return templates.TemplateResponse(
            request,
            "partials/search_results.html",
            {"results": results, "query": req.query, "namespace": req.namespace},
        )

    @router.get("/reports")
    def reports_page(
        request: Request,
        namespace: str | None = None,
        registry: NamespaceRegistry = Depends(get_registry),
    ):
        ns_obj = registry.get(namespace) if namespace else None
        return templates.TemplateResponse(
            request,
            "report.html",
            {
                "namespaces": registry.list_all(),
                "selected_namespace": namespace or "",
                "ns_obj": ns_obj,
                "result": None,
                "form": None,
            },
        )

    @router.post("/reports/generate")
    async def reports_generate_html(
        request: Request,
        registry: NamespaceRegistry = Depends(get_registry),
        storage=Depends(get_storage),
    ):
        from ..services.validation import ReportRequest
        from ..services.reports import generate_report

        form = await request.form()
        try:
            req = ReportRequest(
                title=form.get("title", ""),
                namespace=form.get("namespace", ""),
                columns=form.getlist("columns"),
                entry_type=form.get("entry_type") or None,
                date_from=form.get("date_from") or None,
                date_to=form.get("date_to") or None,
                max_rows=int(form.get("max_rows") or 1000),
                format=form.get("format", "html"),
            )
        except Exception as e:
            raise AppError(f"Invalid report request: {e}", status_code=422)

        if registry.get(req.namespace) is None:
            raise AppError(f"Namespace '{req.namespace}' not found", status_code=404)

        result = generate_report(storage, req)

        return templates.TemplateResponse(
            request,
            "report.html",
            {
                "namespaces": registry.list_all(),
                "selected_namespace": req.namespace,
                "ns_obj": registry.get(req.namespace),
                "result": result,
                "form": req,
            },
        )

    return router
