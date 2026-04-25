import logging
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def install_error_handlers(app, templates: Jinja2Templates):
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.message},
            )
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                f'<div class="text-red-600 text-sm" data-error>{exc.message}</div>',
                status_code=exc.status_code,
            )
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": exc.message, "status_code": exc.status_code},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s", request.url.path)
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"},
            )
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": "Internal server error", "status_code": 500},
            status_code=500,
        )
