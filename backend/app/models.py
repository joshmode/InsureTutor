from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


Language = Literal["en", "zh-Hans", "zh-Hant"]


class Citation(BaseModel):
    id: str
    document: str
    page: int
    section: str | None = None
    excerpt: str
    score: float | None = None


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: Language = "en"
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)

    @field_validator("message")
    @classmethod
    def message_has_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be empty")
        return value.strip()


class ChatResponse(BaseModel):
    message: str
    citations: list[Citation] = Field(default_factory=list)
    language: Language
    kind: Literal["answer", "scope", "insufficient", "blocked", "advice"] = "answer"
    used_retrieval: bool = False
    retrieval_mode: str | None = None
    confidence: float | None = None
    notices: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    llm_configured: bool
    retrieval_mode: str
    documents: int
    chunks: int
    ingest_ready: bool


class SourceChunk(BaseModel):
    id: str
    document: str
    page: int
    section: str
    content: str
    score: float = 0

