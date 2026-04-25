from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .errors import install_error_handlers
from .routers import pages

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Vector DB Web UI")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    install_error_handlers(app, templates)

    app.include_router(pages.register(templates))

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


app = create_app()
