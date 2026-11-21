from __future__ import annotations

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest

from backend.app.api.protection import ProtectionMiddleware
from backend.app.chat.llm import (
    LLMQuotaExceeded,
    LLMInputTooLarge,
    OpenAICompatibleClient,
)
from backend.app.config import Settings
from backend.app.services.consumption import ConsumptionGuard, LimitExceeded


def settings(tmp_path, **kwargs):
    return Settings(data_dir=tmp_path, _env_file=None, **kwargs)


def test_durable_allowances_and_atomic_worker_concurrency(tmp_path):
    config = settings(tmp_path, chat_concurrency_limit=2, chat_requests_per_day=2)
    guards = [ConsumptionGuard(config), ConsumptionGuard(config)]

    def enter(index):
        try:
            return guards[index % 2].admit_chat(str(index))
        except LimitExceeded:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        admitted = list(pool.map(enter, range(8)))
    assert len([x for x in admitted if x]) == 2
    for lease in filter(None, admitted):
        guards[0].release_chat(lease)
    # Restarting / using a fresh process view cannot reset the daily allowance.
    with pytest.raises(LimitExceeded, match="chat_daily"):
        ConsumptionGuard(config).admit_chat("fresh-peer")


def test_forwarded_ip_does_not_evade_peer_rate_limit(tmp_path):
    config = settings(tmp_path, chat_requests_per_minute=1)
    guard = ConsumptionGuard(config)
    assert run_boundary(config, guard, [(b"x-forwarded-for", b"1.2.3.4")])[0] == 200
    result = run_boundary(config, guard, [(b"x-forwarded-for", b"5.6.7.8")])
    assert result[0] == 429
    assert b"retry-after" in dict(result[1])


def run_boundary(config, guard, headers=(), chunks=(b"{}",), failing=False):
    sent, called = [], []

    async def app(scope, receive, send):
        called.append(True)
        message = await receive()
        assert message["body"] == b"".join(chunks)
        if failing:
            raise RuntimeError("private-trace")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    middleware = ProtectionMiddleware(app, config, config.data_dir / "empty-export")
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/chat",
        "scheme": "https",
        "client": ("peer", 1),
        "headers": list(headers),
        "app": SimpleNamespace(state=SimpleNamespace(consumption=guard)),
    }
    items = [
        {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
        for i, chunk in enumerate(chunks)
    ]

    async def receive():
        return items.pop(0) if items else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))
    return (
        sent[0]["status"],
        sent[0]["headers"],
        b"".join(m.get("body", b"") for m in sent),
        called,
    )


@pytest.mark.parametrize(
    "headers,chunks",
    [
        ([(b"content-length", b"2048")], [b"{}"]),
        ([], [b"x" * 600, b"y" * 600]),
        ([(b"content-length", b"2")], [b"x" * 1100]),
    ],
)
def test_body_limit_before_parsing_even_if_chunked_or_false_length(
    tmp_path, headers, chunks
):
    config = settings(tmp_path, max_request_bytes=1024)
    result = run_boundary(config, ConsumptionGuard(config), headers, chunks)
    assert result[0] == 413
    assert not result[3]


def test_auth_security_headers_and_opaque_errors(tmp_path):
    config = settings(
        tmp_path, app_access_username="operator", app_access_password="test-password"
    )
    guard = ConsumptionGuard(config)
    denied = run_boundary(config, guard)
    assert denied[0] == 401 and not denied[3]
    credential = base64.b64encode(b"operator:test-password")
    failed = run_boundary(
        config, guard, [(b"authorization", b"Basic " + credential)], failing=True
    )
    assert failed[0] == 503 and b"private-trace" not in failed[2]
    headers = dict(failed[1])
    assert headers[b"cache-control"] == b"no-store"
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert b"frame-ancestors 'none'" in headers[b"content-security-policy"]
    assert b"script-src 'self'" in headers[b"content-security-policy"]
    assert b"strict-transport-security" in headers
    lease = guard.admit_chat("still-available")
    guard.release_chat(lease)


def test_input_and_output_budgets_prevent_network_calls(tmp_path, monkeypatch):
    import backend.app.chat.llm as module

    config = settings(
        tmp_path,
        llm_api_key="test-only",
        provider_calls_per_day=1,
        provider_output_tokens_per_day=1200,
    )
    guard = ConsumptionGuard(config)
    count = []
    original = httpx.AsyncClient

    def handle(request):
        count.append(True)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "answer"}}]}
        )

    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handle), **kw),
    )
    client = OpenAICompatibleClient(config, consumption=guard)
    asyncio.run(client.complete([{"role": "user", "content": "test"}]))
    with pytest.raises(LLMQuotaExceeded):
        asyncio.run(client.complete([{"role": "user", "content": "second"}]))
    assert len(count) == 1
    with pytest.raises(LLMInputTooLarge):
        asyncio.run(client.complete([{"role": "user", "content": "x" * 65000}]))
    assert len(count) == 1


def test_body_read_timeout_and_cancellation_release_lease(tmp_path):
    config = settings(
        tmp_path, request_read_timeout_seconds=1, chat_concurrency_limit=1
    )
    guard = ConsumptionGuard(config)

    async def exercise(cancel):
        sent = []

        async def app(scope, receive, send):
            raise AssertionError("body never completed")

        boundary = ProtectionMiddleware(app, config, config.data_dir / "empty")
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/chat",
            "client": ("peer", 1),
            "headers": [],
            "app": SimpleNamespace(state=SimpleNamespace(consumption=guard)),
        }

        async def receive():
            await asyncio.Event().wait()

        async def send(message):
            sent.append(message)

        task = asyncio.create_task(boundary(scope, receive, send))
        if cancel:
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task
            assert sent[0]["status"] == 504
        lease = guard.admit_chat("another")
        guard.release_chat(lease)

    asyncio.run(exercise(False))
    asyncio.run(exercise(True))


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://public.example/v1",
        "ftp://public.example",
        "https://user:password@example.com/v1",
        "https://example.com/v1?key=secret",
    ],
)
def test_remote_provider_configuration_requires_tls_and_separates_credentials(endpoint):
    with pytest.raises(ValueError):
        Settings(llm_base_url=endpoint, _env_file=None)


def test_loopback_provider_can_be_used_for_controlled_integration_tests():
    assert Settings(
        llm_base_url="http://127.0.0.1:8999/v1", _env_file=None
    ).llm_base_url.endswith("/v1")


@pytest.mark.parametrize("quota,status", [(True, 429), (False, 413)])
def test_model_limits_are_transport_errors_not_false_brochure_insufficiency(
    quota, status
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api.routes import router

    class Answer:
        async def answer(self, payload):
            if quota:
                raise LLMQuotaExceeded("private quota details", retry_after=120)
            raise LLMInputTooLarge("private length details")

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.runtime = SimpleNamespace(
        ready=True,
        orchestrator=Answer(),
        settings=SimpleNamespace(max_message_chars=4000),
    )
    with TestClient(app) as client:
        result = client.post(
            "/api/chat", json={"message": "What is the interest rate?"}
        )
    assert result.status_code == status and "private" not in result.text
    if quota:
        assert result.headers["retry-after"] == "120"
