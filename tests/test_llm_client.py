from __future__ import annotations

import asyncio

import httpx
import pytest

from backend.app.chat.llm import LLMError, OpenAICompatibleClient
from backend.app.config import Settings


def client_with_transport(monkeypatch, handler, **settings):
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
            **settings,
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
        assert "reasoning_effort" not in payload
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "answer [S1]"}}]}
        )

    client = client_with_transport(monkeypatch, respond)
    answer = asyncio.run(client.complete([{"role": "user", "content": "question"}]))
    assert answer.text == "answer [S1]"


@pytest.mark.parametrize("effort", ["none", "low", ""])
def test_optional_reasoning_effort_is_sent_only_when_configured(monkeypatch, effort):
    import json

    def respond(request):
        payload = json.loads(request.content)
        if effort:
            assert payload["reasoning_effort"] == effort
        else:
            assert "reasoning_effort" not in payload
        return httpx.Response(200, json={"choices": [{"message": {"content": "answer"}}]})

    client = client_with_transport(monkeypatch, respond, llm_reasoning_effort=effort)
    assert asyncio.run(client.complete([])).text == "answer"


def test_unsupported_reasoning_effort_fails_configuration_validation():
    with pytest.raises(ValueError):
        Settings(llm_reasoning_effort="unsupported", _env_file=None)


@pytest.mark.parametrize(
    "payload", [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]}]
)
def test_malformed_provider_response_is_a_controlled_error(monkeypatch, payload):
    client = client_with_transport(
        monkeypatch, lambda request: httpx.Response(200, json=payload)
    )
    with pytest.raises(LLMError):
        asyncio.run(client.complete([]))


@pytest.mark.parametrize("content", [None, "A partly completed explanation [S1]."])
def test_output_limit_rejects_even_nonempty_truncated_completion(monkeypatch, content):
    client = client_with_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}, "finish_reason": "length"}]},
        ),
    )
    with pytest.raises(LLMError, match="output token limit"):
        asyncio.run(client.complete([]))


@pytest.mark.parametrize("content", [None, "A partial explanation"])
def test_stream_reports_truncation_instead_of_success(monkeypatch, content):
    import json

    events = [
        {"choices": [{"delta": {"content": content}, "finish_reason": None}]},
        {"choices": [{"delta": {}, "finish_reason": "length"}]},
    ]
    client = client_with_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200, text="".join("data: " + json.dumps(event) + "\n\n" for event in events)
        ),
    )

    async def consume():
        return [chunk async for chunk in client.stream([])]

    with pytest.raises(LLMError, match="output token limit"):
        asyncio.run(consume())


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
