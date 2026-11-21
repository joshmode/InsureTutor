from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
from starlette.concurrency import run_in_threadpool
from ..services.consumption import LimitExceeded

from ..config import Settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class LLMQuotaExceeded(LLMError):
    def __init__(self, message: str, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(message)


class LLMInputTooLarge(LLMError):
    pass


class LLMNotConfigured(LLMError):
    pass


def _reject_truncated(choice: dict) -> None:
    if choice.get("finish_reason") == "length":
        logger.warning("Model provider reached the output token limit")
        raise LLMError("Model provider reached the output token limit")


@dataclass
class LLMResponse:
    text: str
    usage: dict | None = None


class OpenAICompatibleClient:
    """Minimal chat-completions client with no provider-specific SDK."""

    def __init__(self, settings: Settings, consumption=None):
        self.consumption = consumption
        self.settings = settings
        self.endpoint = f"{settings.llm_base_url.rstrip('/')}/chat/completions"

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.llm_api_key.strip() and self.settings.llm_model.strip()
        )

    def _headers(self) -> dict[str, str]:
        if not self.configured:
            raise LLMNotConfigured("LLM_API_KEY and LLM_MODEL must be configured")
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
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
                self.settings.llm_temperature if temperature is None else temperature
            ),
            "max_tokens": self.settings.llm_max_output_tokens,
            "stream": stream,
        }

    async def _reserve(self, messages, stream, temperature):
        self._headers()
        payload = self._payload(messages, stream=stream, temperature=temperature)
        if (
            len(json.dumps(payload, ensure_ascii=False).encode())
            > self.settings.max_provider_input_bytes
        ):
            raise LLMInputTooLarge("Model input exceeds the configured bound")
        if self.consumption:
            try:
                await run_in_threadpool(
                    self.consumption.reserve_provider_call,
                    self.settings.llm_max_output_tokens,
                )
            except LimitExceeded as exc:
                raise LLMQuotaExceeded(
                    "Model allowance exhausted", exc.retry_after
                ) from exc
        return payload

    async def _bounded_chunks(self, response):
        if response.headers.get("content-encoding", "identity").lower() not in {
            "",
            "identity",
        }:
            raise LLMError("Model response ignored identity encoding")
        count = 0
        async for chunk in response.aiter_bytes():
            count += len(chunk)
            if count > self.settings.max_provider_response_bytes:
                raise LLMError("Model response exceeded the configured bound")
            yield chunk

    async def _bounded_lines(self, response):
        buffer = b""
        async for chunk in self._bounded_chunks(response):
            lines = (buffer + chunk).split(b"\n")
            buffer = lines.pop()
            for line in lines:
                yield line.decode("utf-8", errors="replace").rstrip("\r")
        if buffer:
            yield buffer.decode("utf-8", errors="replace")

    async def complete(
        self,
        messages: list[dict],
        *,
        temperature: float | None = None,
    ) -> LLMResponse:
        payload = await self._reserve(messages, False, temperature)
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.llm_timeout_seconds)
            ) as client:
                async with client.stream(
                    "POST", self.endpoint, headers=self._headers(), json=payload
                ) as response:
                    if response.status_code >= 400:
                        raise LLMError(
                            f"Model provider returned HTTP {response.status_code}"
                        )
                    body = bytearray()
                    async for chunk in self._bounded_chunks(response):
                        body.extend(chunk)
        except httpx.TimeoutException as exc:
            raise LLMError("Model provider timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError("Model provider connection failed") from exc
        try:
            data = json.loads(body)
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected chat-completions response shape") from exc
        _reject_truncated(choice)
        if isinstance(content, list):
            content = "".join(
                str(part.get("text", "")) for part in content if isinstance(part, dict)
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
        payload = await self._reserve(messages, True, temperature)
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.llm_timeout_seconds)
            ) as client:
                async with client.stream(
                    "POST",
                    self.endpoint,
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        raise LLMError(
                            f"Model provider returned HTTP {response.status_code}"
                        )
                    async for line in self._bounded_lines(response):
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if not raw or raw == "[DONE]":
                            continue
                        try:
                            event = json.loads(raw)
                            choice = event["choices"][0]
                            _reject_truncated(choice)
                            delta = choice.get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield str(content)
                        except (ValueError, KeyError, IndexError, TypeError):
                            logger.debug("Skipping malformed SSE event")
        except httpx.TimeoutException as exc:
            raise LLMError("Model provider timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError("Model provider connection failed") from exc
