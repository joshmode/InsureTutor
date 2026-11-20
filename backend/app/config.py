from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven runtime configuration.

    The LLM provider is intentionally generic. Nothing in retrieval needs an
    embedding endpoint from that provider.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_temperature: float = Field(default=0.1, ge=0, le=1.5)
    llm_max_output_tokens: int = Field(default=1200, ge=128, le=8000)
    llm_timeout_seconds: float = Field(default=60, ge=5, le=180)
    llm_extra_headers: str = ""

    knowledge_base_dir: Path = Path("knowledge")
    documents: str = "FLEXI-ULife Prime Saver.pdf"
    data_dir: Path = Path("data/runtime")
    ingest_on_startup: bool = True

    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_enabled: bool = True
    embedding_allow_download: bool = False
    embedding_cache_dir: Path = Path("data/model-cache")
    embedding_batch_size: int = Field(default=32, ge=1, le=128)

    enable_embeddings: bool = True
    hybrid_vector_weight: float = Field(default=0.55, ge=0, le=1)
    hybrid_lexical_weight: float = Field(default=0.45, ge=0, le=1)
    retrieval_top_k: int = Field(default=6, ge=2, le=12)
    retrieval_candidate_limit: int = Field(default=16, ge=4, le=50)
    min_relevance_score: float = Field(default=0.18, ge=0, le=1)
    min_support_score: float = Field(default=0.30, ge=0, le=1)
    max_context_chunks: int = Field(default=6, ge=2, le=10)

    max_message_chars: int = Field(default=4000, ge=100, le=20_000)
    max_history_turns: int = Field(default=8, ge=1, le=30)
    max_retrieval_queries: int = Field(default=4, ge=1, le=8)
    @field_validator("documents")
    @classmethod
    def _documents_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("DOCUMENTS must include at least one PDF")
        return value

    @property
    def document_names(self) -> list[str]:
        return [item.strip() for item in self.documents.split(",") if item.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @property
    def parsed_extra_headers(self) -> dict[str, str]:
        if not self.llm_extra_headers.strip():
            return {}
        headers: dict[str, str] = {}
        for pair in self.llm_extra_headers.split(";"):
            if ":" not in pair:
                continue
            key, value = pair.split(":", 1)
            headers[key.strip()] = value.strip()
        return headers


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

