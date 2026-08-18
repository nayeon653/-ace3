"""통합 청크를 CLOVA bge-m3로 임베딩해 Qdrant에 적재한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from importlib.metadata import version
from pathlib import Path

from pension_agent.config import (
    BGE_M3_INDEXING_CONFIG,
    ClovaStudioConnection,
    QdrantConnection,
)
from pension_agent.ingest.qdrant_indexer import (
    EmbeddingCache,
    IndexProgress,
    QdrantIndexingError,
    ensure_collection,
    index_chunks,
)
from pension_agent.ingest.qdrant_input import CorpusInput, IndexInputError, load_corpus
from pension_agent.retrieval import create_clova_document_embedder, create_qdrant_client
from pension_agent.retrieval.clova_embedder import ClovaEmbeddingFactoryError

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_ROOT = REPO_ROOT / "data" / "indexes" / "pension_documents_v1"
DEFAULT_CHUNKS = INDEX_ROOT / "input" / "chunks.jsonl"
DEFAULT_SOURCE_MANIFESTS = [
    INDEX_ROOT / "input" / "knowledge_sources.jsonl",
    INDEX_ROOT / "input" / "prospectus_sources.jsonl",
]
DEFAULT_CACHE = INDEX_ROOT / "embedding_cache.sqlite3"
DEFAULT_BUILD_MANIFEST = INDEX_ROOT / "manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "load"))
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument(
        "--source-manifest",
        action="append",
        type=Path,
        dest="source_manifests",
        help="반복 지정할 수 있습니다. 생략하면 두 기본 manifest를 사용합니다.",
    )
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--embedding-workers", type=int, default=4)
    parser.add_argument("--requests-per-minute", type=int, default=55)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_BUILD_MANIFEST)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_manifests = args.source_manifests or DEFAULT_SOURCE_MANIFESTS
    try:
        corpus = load_corpus(args.chunks, source_manifests)
        if args.command == "validate":
            print(
                json.dumps(
                    {
                        "status": "valid",
                        "sources": corpus.source_count,
                        "canonical_documents": corpus.canonical_document_count,
                        "chunks": len(corpus.chunks),
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        qdrant_connection = QdrantConnection()
        embedding_config = BGE_M3_INDEXING_CONFIG
        qdrant = create_qdrant_client(qdrant_connection)
        try:
            created = ensure_collection(
                qdrant,
                collection_name=qdrant_connection.collection,
                dense_dimensions=embedding_config.dimensions,
            )
            embedder = create_clova_document_embedder(
                config=embedding_config,
                connection=ClovaStudioConnection(),
                max_workers=args.embedding_workers,
                requests_per_minute=args.requests_per_minute,
            )
            with EmbeddingCache(args.cache) as cache:
                result = index_chunks(
                    qdrant,
                    collection_name=qdrant_connection.collection,
                    chunks=corpus.chunks,
                    embedder=embedder,
                    embedding_model=embedding_config.model,
                    dense_dimensions=embedding_config.dimensions,
                    cache=cache,
                    batch_size=args.batch_size,
                    limit=args.limit,
                    progress=_print_progress,
                )
        finally:
            qdrant.close()

        if result.complete:
            _write_build_manifest(
                args.manifest_output,
                collection_name=qdrant_connection.collection,
                corpus=corpus,
                chunks_path=args.chunks,
                source_manifest_paths=source_manifests,
            )

        print(
            json.dumps(
                {
                    "status": "complete" if result.complete else "partial",
                    "collection_created": created,
                    "processed": result.processed,
                    "total_input_chunks": result.total_input_chunks,
                    "embedded": result.embedded,
                    "cache_hits": result.cache_hits,
                    "collection_points": result.collection_points,
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (
        ClovaEmbeddingFactoryError,
        IndexInputError,
        QdrantIndexingError,
        ValueError,
    ) as exc:
        print(f"indexing failed: {exc}", file=sys.stderr)
        return 1


def _print_progress(progress: IndexProgress) -> None:
    print(
        (
            f"indexed {progress.processed}/{progress.total} "
            f"(embedded={progress.embedded}, cache_hits={progress.cache_hits})"
        ),
        file=sys.stderr,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_build_manifest(
    path: Path,
    *,
    collection_name: str,
    corpus: CorpusInput,
    chunks_path: Path,
    source_manifest_paths: list[Path],
) -> None:
    payload = {
        "collection_name": collection_name,
        "schema_version": "qdrant-hybrid-v1",
        "chunking_version": "docling-hybrid-v1",
        "point_id": "uuid5-url-urn:ace3:chunk:<source_chunk_id>",
        "counts": {
            "sources": corpus.source_count,
            "canonical_documents": corpus.canonical_document_count,
            "points": len(corpus.chunks),
        },
        "inputs": {
            "chunks": {"path": str(chunks_path), "sha256": _sha256(chunks_path)},
            "source_manifests": [
                {"path": str(source_path), "sha256": _sha256(source_path)}
                for source_path in source_manifest_paths
            ],
        },
        "dense": {
            "model": "clova-studio/bge-m3",
            "size": 1024,
            "distance": "cosine",
        },
        "sparse": {
            "model": "qdrant/bm25",
            "preprocessor": "kiwi-content-v1",
            "kiwipiepy_version": version("kiwipiepy"),
            "modifier": "idf",
            "tokenizer": "whitespace",
            "lowercase": True,
            "stemmer": "none",
            "stopwords": [],
            "k": 1.2,
            "b": 0.75,
            "avg_len": 256,
        },
        "fusion": "rrf",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
