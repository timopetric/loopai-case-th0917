"""App factory: create_app(), health probe, /api/v1 mount, SPA static serving."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.v1.router import api_router
from app.config import get_settings
from app.logging_setup import configure_logging

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="loopai — reporting builder", version="0.1.0")

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        """Unauthenticated liveness probe. Always 200 while the process is up."""
        return {"status": "ok"}

    app.include_router(api_router, prefix="/api/v1")

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA from the same origin, with a fallback to index.html
    for client-side routes (deep links)."""
    if not FRONTEND_DIST.is_dir():
        logger.warning(
            "frontend/dist not found at {}; run `make frontend` build or "
            "the Docker image build stage before serving the SPA.",
            FRONTEND_DIST,
        )
        return

    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="frontend-assets",
    )

    index_file = FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        # Never swallow an unmatched API/health path into the SPA shell — a
        # typo'd endpoint should 404, not silently return index.html.
        if full_path.startswith("api/") or full_path == "healthz":
            raise HTTPException(status_code=404)

        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)


app = create_app()
