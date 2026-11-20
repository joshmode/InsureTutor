from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from ..models import ChatRequest, ChatResponse, HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter()


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
    )


@router.get("/chunks/{chunk_id}")
async def get_chunk(chunk_id: str, request: Request) -> dict:
    runtime = request.app.state.runtime
    for chunk in runtime.knowledge.chunks:
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
        return await runtime.orchestrator.answer(payload)
    except Exception:
        logger.exception("Unhandled chat error")
        raise HTTPException(
            status_code=502,
            detail="The tutor could not complete the request. Please try again.",
        ) from None

