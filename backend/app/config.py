from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
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
        hide_input_in_errors=True,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    llm_api_key: str = Field(default="", repr=False)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_temperature: float = Field(default=0.1, ge=0, le=1.5)
    llm_max_output_tokens: int = Field(default=1200, ge=128, le=8000)
    llm_timeout_seconds: float = Field(default=60, ge=5, le=180)
    llm_extra_headers: str = Field(default="", repr=False)

    knowledge_base_dir: Path = Path("knowledge")
    documents: str = "FLEXI-ULife Prime Saver.pdf"
    data_dir: Path = Path("data/runtime")
    ingest_on_startup: bool = True

    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_enabled: bool = True
    embedding_allow_download: bool = False
    embedding_cache_dir: Path = Path("data/model-cache")
    embedding_local_model_dir: Path | None = None
    embedding_batch_size: int = Field(default=32, ge=1, le=128)

    enable_embeddings: bool = True
    hybrid_vector_weight: float = Field(default=0.55, ge=0, le=1)
    hybrid_lexical_weight: float = Field(default=0.45, ge=0, le=1)
    retrieval_top_k: int = Field(default=6, ge=2, le=12)
    retrieval_candidate_limit: int = Field(default=16, ge=4, le=50)
    min_relevance_score: float = Field(default=0.18, ge=0, le=1)
    max_context_chunks: int = Field(default=6, ge=2, le=10)

    # Bounded anonymous demo; counters persist in DATA_DIR across restarts.
    max_request_bytes: int = Field(default=262144, ge=1024, le=1048576)
    request_read_timeout_seconds: float = Field(default=10, ge=1, le=30)
    chat_timeout_seconds: float = Field(default=180, ge=1, le=600)
    chat_requests_per_minute: int = Field(default=20, ge=1, le=1000)
    chat_requests_per_day: int = Field(default=500, ge=1, le=100000)
    chat_concurrency_limit: int = Field(default=4, ge=1, le=32)
    provider_calls_per_day: int = Field(default=300, ge=1, le=100000)
    provider_output_tokens_per_day: int = Field(default=360000, ge=128)
    max_provider_response_bytes: int = Field(default=262144, ge=1024, le=4194304)
    max_provider_input_bytes: int = Field(default=64000, ge=1024, le=262144)
    # Optional browser-native access control; use only behind HTTPS remotely.
    app_access_username: str = ""
    app_access_password: str = Field(default="", repr=False)

    @field_validator("llm_base_url")
    @classmethod
    def _safe_model_endpoint(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "LLM_BASE_URL must be a base URL without embedded credentials, query or fragment"
            )
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("LLM_BASE_URL requires HTTPS except for loopback testing")
        return value

    @model_validator(mode="after")
    def _access_credentials(self):
        if bool(self.app_access_username) != bool(self.app_access_password):
            raise ValueError(
                "Configure both APP_ACCESS_USERNAME and APP_ACCESS_PASSWORD"
            )
        if ":" in self.app_access_username:
            raise ValueError("APP_ACCESS_USERNAME cannot contain a colon")
        return self

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
        return [
            item.strip() for item in self.allowed_origins.split(",") if item.strip()
        ]

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
