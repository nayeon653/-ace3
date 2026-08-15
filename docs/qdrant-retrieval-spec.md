# Qdrant payload와 검색 계약

Docling 청크를 Qdrant에 저장하고 hybrid 검색하는 계약이다. 실제 적재 전에도 이
문서를 기준으로 Repository와 fixture를 구현할 수 있어야 한다.

현재 문서는 공모전 중 변경되지 않고 파일명이 서로 중복되지 않는다고 가정한다.

## 결정 요약

| 구분 | 결정 |
| --- | --- |
| Point ID | 청크마다 생성한 UUID. payload에 중복 저장하지 않음 |
| Dense vector | `dense`, CLOVA Studio `bge-m3`, 1,024차원, cosine |
| Sparse vector | `sparse`, Kiwi 전처리 + `qdrant/bm25`, IDF modifier |
| Hybrid 결합 | Query API의 RRF |
| 문서 식별 | `source_file_name` |
| 문서 분류 | `fund_prospectus`, `pension_reference` |
| 인용 본문 | `content` |
| 검색 입력 | `embedding_content` |
| 제목·위치 | `heading_path`, `page_numbers`에서 응답 시 파생 |

청크 크기·overlap, 파싱·청킹 구현과 실제 적재는 이 문서의 범위가 아니다.

## Point schema

한 Point에 같은 청크의 dense와 sparse vector를 함께 저장한다.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "vector": {
    "dense": [0.012, -0.034, 0.056],
    "sparse": {
      "indices": [14, 125, 973],
      "values": [0.8, 1.2, 0.4]
    }
  },
  "payload": {
    "source_file_name": "R2_KR555202013M.pdf",
    "source_format": "pdf",
    "document_type": "fund_prospectus",
    "chunk_index": 17,
    "content": "이 투자신탁은 원금 손실이 발생할 수 있습니다.",
    "embedding_content": "투자위험\n이 투자신탁은 원금 손실이 발생할 수 있습니다.",
    "heading_path": ["제2부 집합투자기구에 관한 사항", "투자위험"],
    "captions": ["표 3. 투자위험 등급 기준"],
    "element_types": ["text", "table"],
    "page_numbers": [12, 13]
  }
}
```

같은 파일을 다시 적재할 때는 `source_file_name`으로 기존 Point를 제거한 후 새 UUID로
적재한다.

## Vector 설정

```python
from qdrant_client import models


client.create_collection(
    collection_name="pension_documents",
    vectors_config={
        "dense": models.VectorParams(
            size=1024,
            distance=models.Distance.COSINE,
        ),
    },
    sparse_vectors_config={
        "sparse": models.SparseVectorParams(
            modifier=models.Modifier.IDF,
        ),
    },
)
```

CLOVA Studio `bge-m3`는 dense vector만 반환한다. Sparse vector는 Kiwi가 만든
형태소 token 문자열을 Qdrant의 server-side BM25에 전달해 생성한다.

Kiwi는 명사·용언·수식언과 영문·한자·숫자·어근만 남긴다. 조사·어미·문장부호는
제외하고 적재와 질의에 같은 함수를 사용한다.

```python
from kiwipiepy import Kiwi


KIWI = Kiwi()
CONTENT_TAG_PREFIXES = ("N", "V", "M")
CONTENT_TAGS = {"SL", "SH", "SN", "XR"}


def to_bm25_text(text: str) -> str:
    return " ".join(
        token.form
        for token in KIWI.tokenize(text)
        if token.tag.startswith(CONTENT_TAG_PREFIXES) or token.tag in CONTENT_TAGS
    )
```

Qdrant는 이미 분리된 token을 다시 분석하지 않도록 `whitespace` tokenizer를 사용한다.
영어 token만 소문자로 정규화하며 Qdrant의 stemming과 stopword 처리는 비활성화한다.

```python
BM25_OPTIONS = models.Bm25Config(
    k=1.2,
    b=0.75,
    avg_len=256,
    tokenizer=models.TokenizerType.WHITESPACE,
    lowercase=True,
    stemmer=models.DisabledStemmerParams(type=models.NoStemmer.NONE),
    stopwords=models.StopwordsSet(),
)
```

Dense는 `embedding_content`를 그대로 사용하고, sparse는 같은 본문을 Kiwi로 전처리한
결과를 사용한다. 전처리 결과를 별도 payload로 저장하지 않는다.

```python
models.PointStruct(
    id=chunk_id,
    vector={
        "dense": dense_vector,
        "sparse": models.Document(
            text=to_bm25_text(embedding_content),
            model="qdrant/bm25",
            options=BM25_OPTIONS,
        ),
    },
    payload=payload,
)
```

Qdrant는 `Document`를 `indices`와 `values`로 변환해 저장한다. 적재할 청크의 Kiwi
결과가 비어 있으면 잘못된 청크로 처리해 적재하지 않는다. 질의 결과만 비어 있으면
sparse prefetch를 생략하고 dense 검색만 수행한다.

### Retrieval build manifest

Point마다 달라지는 payload가 아니라, collection 전체에 적용한 생성 설정을 기록하는
파일이다. 다음 경로처럼 적재 결과 옆에 한 번만 저장한다.

```text
data/processed/retrieval/pension_documents_v1/manifest.json
```

```json
{
  "collection_name": "pension_documents_v1",
  "schema_version": "qdrant-hybrid-v1",
  "chunking_version": "docling-hybrid-v1",
  "dense": {
    "model": "clova-studio/bge-m3",
    "size": 1024,
    "distance": "cosine"
  },
  "sparse": {
    "model": "qdrant/bm25",
    "preprocessor": "kiwi-content-v1",
    "kiwipiepy_version": "0.23.2",
    "pos_prefixes": ["N", "V", "M"],
    "pos_tags": ["SL", "SH", "SN", "XR"],
    "modifier": "idf",
    "tokenizer": "whitespace",
    "lowercase": true,
    "stemmer": "none",
    "stopwords": [],
    "k": 1.2,
    "b": 0.75,
    "avg_len": 256
  },
  "fusion": "rrf"
}
```

모델, 차원, 청킹 또는 전처리가 바뀌면 기존 collection에 섞어 넣지 않고 새
collection을 만들어 전체 문서를 다시 적재한다.

## Payload

| 필드 | 자료형 | 생성 값 | 용도 |
| --- | --- | --- | --- |
| `source_file_name` | `str` | 원본 파일명 | 문서 식별·내부 검색 |
| `source_format` | `str` | 소문자 확장자 | 위치 표시 방식 구분 |
| `document_type` | `DocumentType` | ingest 분류값 | 문서군 필터 |
| `chunk_index` | `int` | 문서별 0 기반 순서 | 순서 복원·인접 조회 |
| `content` | `str` | `DocChunk.text` | 인용·응답 |
| `embedding_content` | `str` | `chunker.contextualize(chunk)` | dense 입력·Kiwi 전처리 원문 |
| `heading_path` | `list[str]` | `meta.headings` | 제목 계층·검색 문맥 |
| `captions` | `list[str]` | `meta.captions` | 표·그림 문맥 |
| `element_types` | `list[str]` | document item label | 요소 필터 |
| `page_numbers` | `list[int]` | provenance page | 원문 위치 |

모든 필드는 필수다. 문자열은 앞뒤 공백을 제거하고 빈 문자열을 허용하지 않는다.
배열에 값이 없으면 필드를 생략하거나 `null`을 넣지 않고 `[]`로 저장한다.
`source_format`의 초기 허용값은 `pdf`, `docx`, `pptx`, `xlsx`다.

### 문서 분류

`document_type`은 본문을 LLM으로 추론하지 않고 ingest 입력 경로에 지정한 규칙으로
결정한다.

```python
from enum import StrEnum


class DocumentType(StrEnum):
    FUND_PROSPECTUS = "fund_prospectus"
    PENSION_REFERENCE = "pension_reference"
```

| 값 | 대상 |
| --- | --- |
| `fund_prospectus` | 펀드의 투자전략·위험·수수료·환매·과세를 담은 공식 투자설명서 |
| `pension_reference` | 퇴직연금·IRP·연금저축의 제도·세금·업무·FAQ 참고자료 |

현재 Drive의 `투자설명서` 문서군은 `fund_prospectus`, `docs` 문서군은
`pension_reference`로 매핑한다. 분류할 수 없는 입력은 적재를 실패시키며 임의의
기본값을 넣지 않는다.

### 본문과 구조

- `content`만 최종 근거로 인용한다.
- `embedding_content`에는 제목, 캡션과 반복 표 헤더가 포함될 수 있다. Sparse 입력은
  이 값에 `to_bm25_text()`를 적용해 생성한다.
- `heading_path`는 큰 제목부터 가까운 제목 순서로 저장한다. `title`은 저장하지 않고
  마지막 원소에서 만든다.
- `captions`는 연결된 표·그림 순서를 유지한다.
- `element_types`는 중복을 제거하되 최초 등장 순서를 유지한다. 허용값은 `title`,
  `section_header`, `text`, `list_item`, `table`, `picture`, `caption`, `formula`, `code`,
  `unknown`이다.
- `page_numbers`는 모든 item의 `prov.page_no`를 중복 제거해 오름차순으로 저장한다.
  페이지는 1부터 시작하며 DOCX처럼 고정 페이지가 없으면 `[]`이다.

`page`, `page_start`, `page_end`, `title`, `locator`는 중복 저장하지 않는다.

## Docling 매핑

| Payload | Docling 또는 ingest 값 |
| --- | --- |
| `source_file_name` | parser manifest의 원본 파일명 |
| `source_format` | parser manifest의 원본 확장자 |
| `document_type` | ingest 입력 경로의 고정 매핑 |
| `chunk_index` | `chunker.chunk()` 결과의 0 기반 순서 |
| `content` | `DocChunk.text` |
| `embedding_content` | `chunker.contextualize(chunk)` |
| `heading_path` | `DocChunk.meta.headings` 또는 `[]` |
| `captions` | `DocChunk.meta.captions` 또는 `[]` |
| `element_types` | `meta.doc_items[*].label` 정규화 결과 |
| `page_numbers` | `meta.doc_items[*].prov[*].page_no`의 정렬된 집합 |

`document.docling.json`은 파싱 품질 검수용 원본으로 보관하지만 현재 검색에서는 다시
조회하지 않는다. 따라서 `doc_item_refs`는 payload에 넣지 않는다.

## 검색 결과 변환

| API 필드 | 변환 규칙 |
| --- | --- |
| `chunk_id` | `str(point.id)` |
| `source_file_name` | `payload.source_file_name` |
| `title` | `heading_path[-1]`, 없으면 파일명 stem |
| `locator` | 페이지, 제목, `chunk_index` 순으로 파생 |
| `content` | `payload.content` |

```python
def make_locator(
    page_numbers: list[int],
    heading_path: list[str],
    chunk_index: int,
) -> str:
    pages = sorted(set(page_numbers))

    if len(pages) == 1:
        return f"{pages[0]}페이지"
    if pages and pages == list(range(pages[0], pages[-1] + 1)):
        return f"{pages[0]}–{pages[-1]}페이지"
    if pages:
        return ", ".join(f"{page}페이지" for page in pages)
    if heading_path:
        return f"{heading_path[-1]} 절"
    return f"문서 내 청크 {chunk_index + 1}"
```

`embedding_content`와 내부 metadata는 평가 API에 노출하지 않는다.

## Payload index

대량 적재 전에 실제 filter에 사용하는 필드만 index한다.

| 필드 | Index | 조회 |
| --- | --- | --- |
| `source_file_name` | `keyword` | 특정 파일 내부 검색 |
| `document_type` | `keyword` | 문서군 제한 |
| `element_types` | `keyword` | 표·그림·텍스트 제한 |
| `chunk_index` | `integer` | 인접 청크 범위 조회 |

`source_format`, `content`, `embedding_content`, `heading_path`, `captions`,
`page_numbers`에는 초기 index를 만들지 않는다.

## 검색 접근 계약

Qdrant SDK 타입은 `pension_agent/retrieval/` 밖으로 노출하지 않는다. 공용 타입은
`core`에 두고 `retrieval`에서 SDK 타입으로 변환한다.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class HybridQuery:
    text: str
    dense: list[float]
```

```python
search_chunks(
    query: HybridQuery,
    *,
    source_file_name: str | None = None,
    document_type: DocumentType | None = None,
    element_types: list[str] | None = None,
    limit: int = 10,
) -> list[SearchHit]

search_within_document(
    query: HybridQuery,
    *,
    source_file_name: str,
    element_types: list[str] | None = None,
    limit: int = 10,
) -> list[SearchHit]

get_neighbor_chunks(
    *,
    source_file_name: str,
    chunk_index: int,
    before: int = 1,
    after: int = 1,
) -> list[Chunk]

get_chunk(chunk_id: str) -> Chunk | None
```

Hybrid 검색은 원문 질의를 dense embedding과 Kiwi token 문자열로 각각 변환한다. 같은
payload filter로 두 결과를 prefetch한 뒤 RRF로 결합한다.

```python
client.query_points(
    collection_name="pension_documents",
    prefetch=[
        models.Prefetch(
            query=models.Document(
                text=to_bm25_text(query.text),
                model="qdrant/bm25",
                options=BM25_OPTIONS,
            ),
            using="sparse",
            limit=30,
            filter=query_filter,
        ),
        models.Prefetch(
            query=query.dense,
            using="dense",
            limit=30,
            filter=query_filter,
        ),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=10,
    with_payload=True,
    with_vectors=False,
)
```

- `element_types`가 여러 개면 하나 이상 포함한 청크를 허용한다.
- 결과는 RRF 점수 내림차순으로 반환한다.
- prefetch 30개와 최종 10개는 초기값이며 평가 결과로 조정한다.
- `to_bm25_text(query.text)`가 비어 있으면 sparse prefetch를 생략한다.
- 인접 청크는 같은 파일에서 `chunk_index` 범위를 조회하고 오름차순으로 반환한다.
- 잘못된 UUID와 누락되거나 잘못된 payload는 retrieval 경계의 데이터 오류로 처리한다.

## 제외 필드

| 필드 | 현재 제외 이유 |
| --- | --- |
| `product_id` | 파일명으로 문서를 유일하게 선택 가능 |
| `document_id`, `document_version_id` | 파일명 변경과 문서 개정이 없음 |
| `source_hash`, `content_hash` | 증분 적재·중복 제거를 하지 않음 |
| `chunking_version` | build manifest에서 collection 단위로 관리 |
| `corpus` | 현재 두 문서군은 `document_type`으로 구분 가능 |
| `title`, `locator`, `page_start`, `page_end` | 저장 필드에서 파생 가능 |
| `doc_item_refs` | Docling item 재조회 기능이 없음 |
| `token_count` | 검색 filter나 API 응답에서 사용하지 않음 |
| `domains`, `section_key` | 신뢰할 수 있는 자동 분류 규칙이 없음 |

다음 요구가 생기면 스키마와 migration을 함께 재검토한다.

- 한 상품의 여러 문서를 함께 검색
- 같은 파일명의 다른 문서 또는 개정본 보관
- 변경된 청크만 다시 임베딩하는 증분 적재
- Docling 표·그림·bounding box 재조회
- 제목이나 페이지 범위의 정확한 filter
- `pension_reference` 안에서 FAQ·세금·업무자료를 별도로 filter

## 관련 자료

- [로컬 Qdrant 실행과 확인](operations/qdrant-local.md)
- [문서 파싱 운영](operations/document-parsing.md)
- [Qdrant payload](https://qdrant.tech/documentation/concepts/payload/)
- [Qdrant indexing](https://qdrant.tech/documentation/manage-data/indexing/)
- [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)
- [Qdrant BM25](https://qdrant.tech/documentation/inference/inference-bm25/)
- [Kiwi·kiwipiepy](https://github.com/bab2min/kiwipiepy)
- [CLOVA Studio 임베딩](https://guide.ncloud-docs.com/docs/ko/clovastudio-explorer03)
- [Docling chunking](https://docling-project.github.io/docling/concepts/chunking/)
- [GitHub 이슈 #33](https://github.com/nayeon653/-ace3/issues/33)
