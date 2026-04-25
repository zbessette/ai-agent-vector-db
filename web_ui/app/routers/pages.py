from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates


def register(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    def dashboard(request: Request):
        return templates.TemplateResponse(request, "dashboard.html")

    return router
