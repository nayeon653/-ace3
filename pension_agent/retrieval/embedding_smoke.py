from __future__ import annotations

import json
from pathlib import Path

from langchain_naver import ClovaXEmbeddings  # type: ignore[import-untyped]

from pension_agent.config import ClovaStudioConnection

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = REPO_ROOT / "data" / "indexes" / "unified" / "chunks.jsonl"


def load_samples(limit: int = 3) -> list[str]:
    samples: list[str] = []

    with CORPUS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            row = json.loads(line)
            text = row["text"].strip()

            if text:
                samples.append(text)

            if len(samples) >= limit:
                break

    return samples


def main() -> None:
    connection = ClovaStudioConnection()

    if connection.api_key is None:
        raise RuntimeError("CLOVASTUDIO_API_KEY is not configured")

    if not connection.api_base_url:
        raise RuntimeError("CLOVASTUDIO_API_BASE_URL is not configured")

    embeddings = ClovaXEmbeddings(
        model="bge-m3",
        api_key=connection.api_key.get_secret_value(),
        base_url=connection.api_base_url,
    )

    texts = load_samples(3)

    print(f"sample_count={len(texts)}")

    vectors = embeddings.embed_documents(texts)

    print(f"vector_count={len(vectors)}")

    for index, vector in enumerate(vectors):
        print(f"sample={index} dimension={len(vector)} first_values={vector[:3]}")

    if len(vectors) != 3:
        raise RuntimeError("expected exactly 3 vectors")

    dimensions = {len(vector) for vector in vectors}

    if len(dimensions) != 1:
        raise RuntimeError(f"inconsistent embedding dimensions: {dimensions}")

    print(f"embedding_dimension={dimensions.pop()}")
    print("SMOKE_TEST=PASS")


if __name__ == "__main__":
    main()
