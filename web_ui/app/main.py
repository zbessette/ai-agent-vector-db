from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Vector DB Web UI")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


app = create_app()
