from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()


def register(templates: Jinja2Templates) -> APIRouter:
    @router.get("/")
    def dashboard(request: Request):
        return templates.TemplateResponse(request, "dashboard.html")

    return router
