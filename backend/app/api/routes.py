from __future__ import annotations

import logging
import asyncio
import re
import secrets
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from ..chat.llm import LLMQuotaExceeded, LLMInputTooLarge
from ..models import ChatRequest, ChatResponse, HealthResponse, BrochureInfo
from ..services.brochures import OWNER_COOKIE, BrochureError

logger = logging.getLogger(__name__)
router = APIRouter()


async def private_context(request: Request, identifier: str):
    try:
        return await run_in_threadpool(
            request.app.state.runtime.brochures.get, identifier,
            request.cookies.get(OWNER_COOKIE, ""),
        )
    except BrochureError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None


@router.post("/brochures", response_model=BrochureInfo, status_code=201,
             openapi_extra={"requestBody": {"required": True, "content": {
                 "application/pdf": {"schema": {"type": "string", "format": "binary"}}
             }}})
async def upload_brochure(request: Request, response: Response):
    if request.headers.get("content-type", "").split(";")[0] != "application/pdf":
        raise HTTPException(status_code=415, detail="Upload a PDF with Content-Type application/pdf.")
    owner = request.cookies.get(OWNER_COOKIE, "")
    if not re.fullmatch(r"[a-f0-9]{64}", owner):
        owner = secrets.token_hex(32)
    store = request.app.state.runtime.brochures
    work = asyncio.create_task(run_in_threadpool(
        store.create, await request.body(),
        unquote(request.headers.get("x-file-name", "brochure.pdf")), owner,
    ))
    try:
        context = await asyncio.shield(work)
    except asyncio.CancelledError:
        # Parsing/indexing runs in a thread; delete its eventual result if the
        # requesting conversation disappears before it receives the ID.
        def cleanup(task):
            if not task.cancelled() and task.exception() is None:
                asyncio.create_task(run_in_threadpool(store.delete, task.result().info.id, owner))
        work.add_done_callback(cleanup)
        raise
    except BrochureError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
    response.set_cookie(OWNER_COOKIE, owner, httponly=True, samesite="strict",
                        secure=store.settings.brochure_cookie_secure or request.url.scheme == "https",
                        max_age=store.settings.brochure_retention_seconds)
    response.headers["Cache-Control"] = "no-store"
    return context.info


@router.delete("/brochures/{brochure_id}", status_code=204)
async def delete_brochure(brochure_id: str, request: Request):
    try:
        await run_in_threadpool(request.app.state.runtime.brochures.delete,
                                brochure_id, request.cookies.get(OWNER_COOKIE, ""))
    except BrochureError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    runtime = request.app.state.runtime
    return HealthResponse(
        status="ok" if runtime.ready else "starting",
        llm_configured=runtime.llm.configured,
        retrieval_mode=runtime.retriever.mode if runtime.retriever else "unavailable",
        documents=len({c.document for c in runtime.knowledge.chunks}),
        chunks=len(runtime.knowledge.chunks),
        ingest_ready=bool(runtime.knowledge.chunks),
        request_timeout_seconds=(
            runtime.settings.chat_timeout_seconds
            + runtime.settings.request_read_timeout_seconds
            + 5
        ),
    )


@router.get("/chunks/{chunk_id}")
async def get_chunk(chunk_id: str, request: Request, brochure_id: str | None = None) -> dict:
    runtime = request.app.state.runtime
    try:
        chunks = (await run_in_threadpool(runtime.brochures.chunks, brochure_id,
                                        request.cookies.get(OWNER_COOKIE, ""))
                  if brochure_id else runtime.knowledge.chunks)
    except BrochureError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
    for chunk in chunks:
        if chunk.id == chunk_id:
            return {
                "id": chunk.id,
                "document": chunk.document,
                "page": chunk.page,
                "section": chunk.section,
                "excerpt": chunk.citation_excerpt,
            }
    raise HTTPException(status_code=404, detail="Source chunk not found")


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    runtime = request.app.state.runtime
    if not runtime.ready or runtime.orchestrator is None:
        raise HTTPException(status_code=503, detail="Knowledge base is still loading")
    if len(payload.message) > runtime.settings.max_message_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Message exceeds {runtime.settings.max_message_chars} characters",
        )
    try:
        orchestrator = ((await private_context(request, payload.brochure_id)).orchestrator
                        if payload.brochure_id else runtime.orchestrator)
        return await orchestrator.answer(payload)
    except HTTPException:
        raise
    except LLMQuotaExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail="The AI allowance is exhausted. Please try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from None
    except LLMInputTooLarge:
        raise HTTPException(
            status_code=413,
            detail="This conversation is too long. Start a new conversation.",
        ) from None
    except Exception:
        logger.exception("Unhandled chat error")
        raise HTTPException(
            status_code=502,
            detail="The tutor could not complete the request. Please try again.",
        ) from None
