"""Bounded HTTP responsiveness check, not a capacity benchmark.

Start an isolated app with documented limits and pass --base-url. Outcomes record
200/429 separately. Health responsiveness must hold while chat is saturated.
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.http_deadline import request_timeout


async def run(base, requests, concurrency):
    gate = asyncio.Semaphore(concurrency)
    health_times, chat_times, statuses = [], [], []
    done = asyncio.Event()
    async with httpx.AsyncClient(base_url=base, timeout=10) as client:
        initial = (await client.get("/api/health")).json()
        assert initial["status"] == "ok"
        client.timeout = httpx.Timeout(request_timeout(initial), connect=10)

        async def health():
            while not done.is_set():
                start = time.perf_counter()
                result = await client.get("/api/health", timeout=5)
                assert result.status_code == 200 and result.json()["status"] == "ok"
                health_times.append((time.perf_counter() - start) * 1000)
                await asyncio.sleep(0.02)

        async def chat():
            async with gate:
                start = time.perf_counter()
                result = await client.post(
                    "/api/chat",
                    json={
                        "message": "Is the 4% interest rate guaranteed?",
                        "language": "en",
                    },
                )
                statuses.append(result.status_code)
                chat_times.append((time.perf_counter() - start) * 1000)

        watcher = asyncio.create_task(health())
        try:
            await asyncio.gather(*(chat() for _ in range(requests)))
        finally:
            done.set()
            await watcher
    percentile = lambda values: sorted(values)[max(0, int(len(values) * 0.95) - 1)]
    return {
        "requests": requests,
        "client_concurrency": concurrency,
        "retrieval_mode": initial["retrieval_mode"],
        "llm_configured": initial["llm_configured"],
        "statuses": {str(s): statuses.count(s) for s in set(statuses)},
        "health_samples": len(health_times),
        "health_p95_ms": round(percentile(health_times), 2),
        "chat_p95_ms": round(percentile(chat_times), 2),
        "passed": all(s in (200, 429) for s in statuses)
        and 200 in statuses
        and percentile(health_times) < 500,
        "scope": f"Local responsiveness under bounded {initial['retrieval_mode']} chat workload; not a language-model quality or production capacity benchmark.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--requests", type=int, default=24)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/audit/load-results.json")
    )
    args = parser.parse_args()
    if not 1 <= args.requests <= 100 or not 1 <= args.concurrency <= 16:
        parser.error("Use at most 100 requests and 16 clients")
    result = asyncio.run(run(args.base_url, args.requests, args.concurrency))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
