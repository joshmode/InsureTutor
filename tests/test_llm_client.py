from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.app.chat.llm import LLMError, OpenAICompatibleClient
from backend.app.config import Settings


def client_with_transport(monkeypatch, handler):
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    return OpenAICompatibleClient(
        Settings(
            llm_api_key="test-only-not-a-secret",
            llm_base_url="https://example.invalid/custom/v1/",
            llm_model="test-model",
            _env_file=None,
        )
    )


def test_configurable_provider_receives_chat_not_embeddings(monkeypatch):
    import json

    def respond(request):
        assert str(request.url) == "https://example.invalid/custom/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-only-not-a-secret"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["messages"] == [{"role": "user", "content": "question"}]
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "answer [S1]"}}]}
        )

    client = client_with_transport(monkeypatch, respond)
    answer = asyncio.run(client.complete([{"role": "user", "content": "question"}]))
    assert answer.text == "answer [S1]"


@pytest.mark.parametrize(
    "payload", [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]}]
)
def test_malformed_provider_response_is_a_controlled_error(monkeypatch, payload):
    client = client_with_transport(
        monkeypatch, lambda request: httpx.Response(200, json=payload)
    )
    with pytest.raises(LLMError):
        asyncio.run(client.complete([]))


def test_provider_error_body_is_not_exposed_in_exception(monkeypatch):
    client = client_with_transport(
        monkeypatch,
        lambda request: httpx.Response(401, text="echoed-sensitive-provider-data"),
    )
    with pytest.raises(LLMError) as error:
        asyncio.run(client.complete([]))
    assert "401" in str(error.value)
    assert "echoed-sensitive-provider-data" not in str(error.value)


def test_oversized_provider_response_is_rejected_before_json_parsing(monkeypatch):
    client = client_with_transport(
        monkeypatch, lambda request: httpx.Response(200, content=b"x" * 263000)
    )
    with pytest.raises(LLMError, match="bound"):
        asyncio.run(client.complete([]))


def test_provider_cannot_force_decompression_of_an_unbounded_reply(monkeypatch):
    import gzip

    client = client_with_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            content=gzip.compress(b"x" * 300000),
            headers={"content-encoding": "gzip"},
        ),
    )
    with pytest.raises(LLMError, match="identity"):
        asyncio.run(client.complete([]))
