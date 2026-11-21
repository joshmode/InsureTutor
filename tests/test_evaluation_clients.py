"""Evaluation clients must wait for the application's configured deadline."""

import asyncio
import json

import httpx
import pytest

from scripts import evaluate_provider, load_smoke


@pytest.mark.parametrize("runner", ["provider", "load"])
def test_evaluation_clients_use_the_advertised_deadline(monkeypatch, runner):
    observed = []

    def handler(request):
        if request.url.path == "/api/health":
            return httpx.Response(200, json={
                "status": "ok", "llm_configured": False,
                "retrieval_mode": "lexical", "request_timeout_seconds": 285,
            })
        observed.append(request.extensions["timeout"]["read"])
        question = json.loads(request.content)["message"]
        case = next((c for c in evaluate_provider.CASES if c["question"] == question), None)
        return httpx.Response(200, json={
            "kind": case["kinds"][0] if case else "answer",
            "citations": [{"excerpt": " ".join(case["evidence"])}] if case else [],
        })

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(
        transport=httpx.MockTransport(handler), **kw,
    ))
    if runner == "provider":
        asyncio.run(evaluate_provider.evaluate("http://test", False))
    else:
        asyncio.run(load_smoke.run("http://test", 2, 1))
    assert observed and set(observed) == {285}


def test_live_evaluation_rejects_excerpt_fallback_even_when_model_is_configured(monkeypatch):
    generated = False

    def handler(request):
        if request.url.path == "/api/health":
            return httpx.Response(200, json={
                "status": "ok", "llm_configured": True,
                "retrieval_mode": "lexical", "request_timeout_seconds": 195,
            })
        question = json.loads(request.content)["message"]
        case = next(c for c in evaluate_provider.CASES if c["question"] == question)
        return httpx.Response(200, json={
            "kind": case["kinds"][0],
            "model_generated": generated and case["kinds"][0] == "answer",
            "citations": [{"excerpt": " ".join(case["evidence"])}],
        })

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(
        transport=httpx.MockTransport(handler), **kw,
    ))
    result = asyncio.run(evaluate_provider.evaluate("http://test", True))
    assert result["mechanical_passed"] < result["total"]
    assert all(not case["passed"] for case in result["cases"] if "answer" in case["kinds"])
    generated = True
    result = asyncio.run(evaluate_provider.evaluate("http://test", True))
    assert result["mechanical_passed"] == result["total"]
    assert result["model_generated_answers"] == 5
