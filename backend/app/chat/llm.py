from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from ..config import Settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class LLMNotConfigured(LLMError):
    pass


@dataclass
class LLMResponse:
    text: str
    usage: dict | None = None


class OpenAICompatibleClient:
    """Minimal chat-completions client with no provider-specific SDK."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.endpoint = f"{settings.llm_base_url.rstrip('/')}/chat/completions"

    @property
    def configured(self) -> bool:
        return bool(self.settings.llm_api_key.strip() and self.settings.llm_model.strip())

    def _headers(self) -> dict[str, str]:
        if not self.configured:
            raise LLMNotConfigured("LLM_API_KEY and LLM_MODEL must be configured")
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.settings.parsed_extra_headers)
        return headers

    def _payload(
        self,
        messages: list[dict],
        *,
        stream: bool,
        temperature: float | None = None,
    ) -> dict:
        return {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": (
                self.settings.llm_temperature
                if temperature is None
                else temperature
            ),
            "max_tokens": self.settings.llm_max_output_tokens,
            "stream": stream,
        }

    async def complete(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
    ) -> LLMResponse:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.llm_timeout_seconds)
            ) as client:
                response = await client.post(
                    self.endpoint,
                    headers=self._headers(),
                    json=self._payload(
                        messages, stream=False, temperature=temperature
                    ),
                )
        except httpx.TimeoutException as exc:
            raise LLMError("Model provider timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Model provider connection failed: {exc}") from exc
        if response.status_code >= 400:
            detail = response.text[:500]
            raise LLMError(
                f"Model provider returned HTTP {response.status_code}: {detail}"
            )
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected chat-completions response shape") from exc
        if isinstance(content, list):
            content = "".join(
                str(part.get("text", ""))
                for part in content
                if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Model provider returned empty content")
        return LLMResponse(text=content.strip(), usage=data.get("usage"))

    async def stream(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.llm_timeout_seconds)
            ) as client:
                async with client.stream(
                    "POST",
                    self.endpoint,
                    headers=self._headers(),
                    json=self._payload(messages, stream=True, temperature=temperature),
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise LLMError(
                            f"Model provider returned HTTP {response.status_code}: "
                            f"{body[:500].decode(errors='replace')}"
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if not raw or raw == "[DONE]":
                            continue
                        try:
                            event = json.loads(raw)
                            delta = event["choices"][0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield str(content)
                        except (ValueError, KeyError, IndexError, TypeError):
                            logger.debug("Skipping malformed SSE event")
        except httpx.TimeoutException as exc:
            raise LLMError("Model provider timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Model provider connection failed: {exc}") from exc

