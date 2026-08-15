from __future__ import annotations

import os
import time

import httpx
from qdrant_client import QdrantClient

DEFAULT_QDRANT_URL = "http://127.0.0.1:6333"
READY_TIMEOUT_SECONDS = 30.0
REQUEST_TIMEOUT_SECONDS = 2.0


def wait_until_ready(url: str) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False) as client:
        while True:
            try:
                response = client.get(f"{url}/readyz")
                response.raise_for_status()
                return
            except httpx.HTTPError as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Qdrant did not become ready within {READY_TIMEOUT_SECONDS:.0f} seconds: {url}"
                    ) from exc
                time.sleep(1.0)


def main() -> None:
    url = os.environ.get("QDRANT_URL", DEFAULT_QDRANT_URL).rstrip("/")
    if not url:
        raise ValueError("QDRANT_URL must not be empty")

    wait_until_ready(url)

    client = QdrantClient(url=url, timeout=REQUEST_TIMEOUT_SECONDS)
    try:
        collections = client.get_collections().collections
    finally:
        client.close()

    print(f"Qdrant ready: {url} ({len(collections)} collections)")


if __name__ == "__main__":
    main()
