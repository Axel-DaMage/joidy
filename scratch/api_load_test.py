from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def fetch(url: str, timeout: float) -> tuple[float, int]:
    request = Request(url, headers={"Accept-Encoding": "gzip"})
    start = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
            status = response.status
    except HTTPError as error:
        error.read()
        status = error.code
    return time.perf_counter() - start, status


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple API load test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8008")
    parser.add_argument("--path", default="/health")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + args.path
    latencies: list[float] = []
    status_counts: dict[int, int] = {}

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(fetch, url, args.timeout) for _ in range(args.requests)]
        for future in as_completed(futures):
            latency, status = future.result()
            latencies.append(latency)
            status_counts[status] = status_counts.get(status, 0) + 1
    elapsed = time.perf_counter() - started

    if not latencies:
        raise SystemExit("no requests completed")

    latencies_ms = [value * 1000 for value in latencies]
    payload = {
        "url": url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "elapsed_s": round(elapsed, 3),
        "throughput_rps": round(args.requests / elapsed, 2),
        "status_counts": status_counts,
        "latency_ms": {
            "min": round(min(latencies_ms), 2),
            "p50": round(statistics.median(latencies_ms), 2),
            "p95": round(sorted(latencies_ms)[max(0, int(len(latencies_ms) * 0.95) - 1)], 2),
            "avg": round(statistics.mean(latencies_ms), 2),
            "max": round(max(latencies_ms), 2),
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()