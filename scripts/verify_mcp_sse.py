#!/usr/bin/env python3
"""Reachability smoke test for the FinMind MCP SSE endpoint."""

from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    url = os.getenv("FINMIND_MCP_SSE_URL", "http://127.0.0.1:9123/sse")
    with httpx.Client(timeout=10) as client:
        with client.stream("GET", url, headers={"Accept": "text/event-stream"}) as response:
            print(f"status={response.status_code} content_type={response.headers.get('content-type')}")
            if response.status_code != 200:
                raise RuntimeError(f"unexpected status: {response.status_code}")
            if "text/event-stream" not in response.headers.get("content-type", ""):
                raise RuntimeError("unexpected content type")
    return 0


if __name__ == "__main__":
    sys.exit(main())
