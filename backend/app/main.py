from __future__ import annotations

import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .api.protection import ProtectionMiddleware
from .services.consumption import ConsumptionGuard
from .config import get_settings
from .logging_config import configure_logging
from .services.runtime import AppRuntime

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.consumption = ConsumptionGuard(settings)
    runtime = AppRuntime(settings, consumption=app.state.consumption)
    app.state.runtime = runtime
    try:
        from starlette.concurrency import run_in_threadpool

        await run_in_threadpool(runtime.initialize)
    except Exception:
        logger.exception("Startup initialization failed")
        raise
    async def prune_uploads():
        while True:
            await asyncio.sleep(60)
            await run_in_threadpool(runtime.brochures.prune)
    cleanup = asyncio.create_task(prune_uploads())
    try:
        yield
    finally:
        cleanup.cancel()
        await asyncio.gather(cleanup, return_exceptions=True)


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
app.add_middleware(ProtectionMiddleware, settings=settings, static_dir=STATIC_DIR)
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
async def source_document(request: Request, document: str | None = None, brochure_id: str | None = None):
    if brochure_id:
        from .api.routes import private_context
        from urllib.parse import quote
        from starlette.concurrency import run_in_threadpool
        context = await private_context(request, brochure_id)
        if document is not None and document != context.info.filename:
            raise HTTPException(status_code=404, detail="Source document not found")
        content = await run_in_threadpool(context.path.read_bytes)
        return Response(content, media_type="application/pdf", headers={
            "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
            "Content-Disposition": "inline; filename*=UTF-8''" + quote(context.info.filename, safe=""),
        })
    names = settings.document_names
    name = document if document is not None else (names[0] if names else "")
    if (
        name not in names
        or Path(name).name != name
        or Path(name).suffix.lower() != ".pdf"
    ):
        raise HTTPException(status_code=404, detail="Source document not found")
    root = settings.knowledge_base_dir.resolve()
    pdf = (root / name).resolve()
    if not pdf.is_relative_to(root) or not pdf.is_file():
        raise HTTPException(status_code=404, detail="Source document not found")
    return FileResponse(pdf, media_type="application/pdf")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    candidate = (STATIC_DIR / full_path).resolve()
    if not candidate.is_relative_to(STATIC_DIR.resolve()):
        raise HTTPException(status_code=404, detail="Not found")
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "message": "InsureTutor API is running. Build the frontend to serve the UI."
    }
