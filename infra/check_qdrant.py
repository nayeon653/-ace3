from __future__ import annotations

import time

import httpx

from pension_agent.config import QdrantConnection
from pension_agent.retrieval import create_qdrant_client

READY_TIMEOUT_SECONDS = 30.0
REQUEST_TIMEOUT_SECONDS = 2.0


def wait_until_ready(url: str, *, api_key: str | None = None) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False) as client:
        while True:
            try:
                headers = {"api-key": api_key} if api_key else None
                response = client.get(f"{url}/readyz", headers=headers)
                response.raise_for_status()
                return
            except httpx.HTTPError as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Qdrant did not become ready within {READY_TIMEOUT_SECONDS:.0f} seconds: {url}"
                    ) from exc
                time.sleep(1.0)


def main() -> None:
    connection = QdrantConnection()
    api_key = connection.api_key.get_secret_value() if connection.api_key is not None else None

    wait_until_ready(connection.url, api_key=api_key)

    client = create_qdrant_client(connection)
    try:
        collections = client.get_collections().collections
    finally:
        client.close()

    print(f"Qdrant ready: {connection.url} ({len(collections)} collections)")


if __name__ == "__main__":
    main()
