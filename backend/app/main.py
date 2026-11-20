from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import get_settings
from .logging_config import configure_logging
from .services.runtime import AppRuntime

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    runtime = AppRuntime(settings)
    app.state.runtime = runtime
    try:
        runtime.initialize()
    except Exception:
        logger.exception("Startup initialization failed")
        raise
    yield


settings = get_settings()
app = FastAPI(
    title="InsureTutor API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")

STATIC_DIR = Path(__file__).resolve().parents[2] / "frontend" / "out"
settings.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.mkdir(parents=True, exist_ok=True)
if STATIC_DIR.exists():
    next_assets = STATIC_DIR / "_next"
    if next_assets.exists():
        app.mount("/_next", StaticFiles(directory=next_assets), name="next-assets")
    for asset_dir in ("assets", "fonts"):
        if (STATIC_DIR / asset_dir).exists():
            app.mount(
                f"/{asset_dir}",
                StaticFiles(directory=STATIC_DIR / asset_dir),
                name=f"static-{asset_dir}",
            )


@app.get("/source-document", include_in_schema=False)
async def source_document():
    pdf = settings.knowledge_base_dir / settings.document_names[0]
    if pdf.exists():
        return FileResponse(pdf, media_type="application/pdf")
    return {"detail": "Source document not available"}


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        return {"detail": "Not found"}
    candidate = STATIC_DIR / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "InsureTutor API is running. Build the frontend to serve the UI."}

