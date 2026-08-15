# Qdrant payload와 검색 계약

이 문서는 Docling 청킹 결과를 Qdrant에 저장하고 검색 계층에서 조회하기 위한
Point, payload, filter와 응답 변환 계약의 단일 원본이다. 실제 청킹·임베딩·적재
파이프라인이 완성되기 전에 조회 코드를 구현하고 fixture로 검증할 수 있도록 경계를
고정한다.

현재 제공 문서는 공모전 중 변경되지 않고 파일명이 서로 중복되지 않는다고 가정한다.
이 가정이 깨지면 [재검토 조건](#재검토-조건)에 따라 식별자와 버전 필드를 추가한다.

## 범위

이 문서에서 결정하는 범위는 다음과 같다.

- Qdrant Point ID와 payload 필드
- Dense·sparse named vector와 hybrid fusion
- Docling 청크에서 payload를 만드는 규칙
- Qdrant payload index
- 문서 내부 검색과 인접 청크 조회 입력·출력
- 평가 API의 근거 응답으로 변환하는 규칙

다음 항목은 이 문서의 범위가 아니다.

- 청크 최대 토큰 수와 overlap 값
- 문서 파싱 및 청킹 구현
- 실제 Qdrant Repository 구현
- 실제 문서와 vector 적재

## Qdrant Point 계약

Qdrant의 Point ID를 `chunk_id`로 사용한다. Point ID는 UUID로 생성하며 payload에
`chunk_id`를 중복 저장하지 않는다. 같은 파일을 다시 적재해야 할 때는
`source_file_name`으로 기존 Point를 제거한 후 새 UUID로 적재한다.

한 Point에 `dense`와 `sparse` named vector를 함께 저장한다. Dense vector는 의미
유사도를, sparse vector는 BM25 기반 어휘 일치도를 계산한다. 두 검색 결과는 Query
API의 RRF로 결합한다.

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
    "source_file_name": "미래에셋_글로벌AI_투자설명서.pdf",
    "source_format": "pdf",
    "document_type": "investment_prospectus",
    "chunk_index": 17,
    "content": "이 투자신탁은 원금 손실이 발생할 수 있습니다.",
    "embedding_content": "제2부 집합투자기구에 관한 사항\n투자위험\n이 투자신탁은 원금 손실이 발생할 수 있습니다.",
    "heading_path": [
      "제2부 집합투자기구에 관한 사항",
      "투자위험"
    ],
    "captions": [
      "표 3. 투자위험 등급 기준"
    ],
    "element_types": [
      "text",
      "table"
    ],
    "page_numbers": [
      12,
      13
    ]
  }
}
```

## Collection vector schema

초기 hybrid 검색은 다음 조합을 사용한다.

| 역할 | 이름 | 모델 | Qdrant 설정 |
| --- | --- | --- | --- |
| 의미 검색 | `dense` | CLOVA Studio Embedding v2 `bge-m3` | 1,024차원, cosine |
| 어휘 검색 | `sparse` | `qdrant/bm25` | Sparse vector, IDF modifier |
| 결과 결합 | - | RRF | Query API fusion |

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

CLOVA Studio Embedding v2의 `bge-m3`는 dense 출력만 반환하므로 sparse vector는
Qdrant의 server-side BM25로 생성한다. `bge-m3`는 한국어를 포함한 다국어 문서에
사용할 수 있고 최대 8,192 token 입력과 1,024차원 출력을 지원한다.

Qdrant BM25의 기본 전처리는 영어 기준이므로 한국어 문서에는 다음 설정을 적재와
질의에 동일하게 적용한다. 이 language-neutral 설정은 Qdrant 1.19 이상을 요구하며
현재 로컬 이미지 `qdrant/qdrant:v1.19.0`과 일치한다.

```python
BM25_OPTIONS = models.Bm25Config(
    k=1.2,
    b=0.75,
    avg_len=256,
    tokenizer=models.TokenizerType.MULTILINGUAL,
    stemmer=models.DisabledStemmerParams(type=models.NoStemmer.NONE),
    stopwords=models.StopwordsSet(),
)
```

적재 파이프라인은 dense vector를 CLOVA Studio에서 생성하고, sparse 입력은 Qdrant가
처리할 `Document`로 전달한다.

```python
models.PointStruct(
    id=chunk_id,
    vector={
        "dense": dense_vector,
        "sparse": models.Document(
            text=embedding_content,
            model="qdrant/bm25",
            options=BM25_OPTIONS,
        ),
    },
    payload=payload,
)
```

Qdrant는 적재 요청의 `Document`를 실제 sparse vector로 변환해 저장한다. 따라서 Point
조회 결과와 이 문서 상단의 저장 예시에는 `indices`와 `values`가 나타난다.

초기에는 dense와 sparse 모두 `embedding_content`를 입력으로 사용한다. 제목이나
반복 표 헤더가 BM25 점수를 과도하게 높이는 것이 평가에서 확인될 때만 sparse 입력을
`heading_path + content`로 분리한다. 입력 조합을 분리하더라도 별도 payload 필드는
추가하지 않는다.

### Retrieval build manifest

모델과 청킹 설정은 모든 Point payload에 반복하지 않고 collection을 만든 적재 작업의
manifest에서 한 번만 관리한다.

```json
{
  "schema_version": "qdrant-hybrid-v1",
  "chunking_version": "docling-hybrid-v1",
  "dense_model": "clova-studio/bge-m3",
  "dense_size": 1024,
  "dense_distance": "cosine",
  "sparse_model": "qdrant/bm25",
  "sparse_modifier": "idf",
  "sparse_k": 1.2,
  "sparse_b": 0.75,
  "sparse_avg_len": 256,
  "sparse_tokenizer": "multilingual",
  "sparse_stemmer": "none",
  "sparse_stopwords": [],
  "fusion": "rrf"
}
```

Dense 모델, 차원, sparse 모델 또는 입력 전처리가 바뀌면 기존 collection에 섞어
적재하지 않고 새 collection을 만들어 전체 문서를 다시 적재한다.

한국어 상품명·조항명·수치 질의에서 BM25의 품질이 부족하다고 평가될 때는 로컬
`BAAI/bge-m3`의 sparse lexical weights를 대안으로 비교한다. CLOVA Studio의
`bge-m3` API는 dense vector만 반환하므로 이 대안은 별도 로컬 추론 운영이 필요하다.

## Payload 필드

| 필드 | 자료형 | 필수 | 생성 주체 | 용도 |
| --- | --- | --- | --- | --- |
| `source_file_name` | `str` | 예 | 수집 단계 | 문서 식별과 특정 파일 내부 검색 |
| `source_format` | `str` | 예 | 수집 단계 | PDF와 Office 문서의 위치 표시 방식 구분 |
| `document_type` | `str` | 예 | 수집 단계 | 투자설명서 등 문서 종류 필터 |
| `chunk_index` | `int` | 예 | 청킹 단계 | 문서 내 순서 복원과 인접 청크 조회 |
| `content` | `str` | 예 | Docling chunk | 사용자에게 인용할 청크 본문 |
| `embedding_content` | `str` | 예 | Docling chunker | vector 생성에 사용한 문맥 보강 본문 |
| `heading_path` | `list[str]` | 예 | Docling chunk metadata | 제목 계층 보존과 임베딩 문맥 보강 |
| `captions` | `list[str]` | 예 | Docling chunk metadata | 표·그림 문맥 보강 |
| `element_types` | `list[str]` | 예 | Docling document item | 표·텍스트 등 요소 종류 필터 |
| `page_numbers` | `list[int]` | 예 | Docling provenance | 원문 페이지 표시 |

모든 문자열은 앞뒤 공백을 제거한 후 저장한다. 필수 문자열은 빈 문자열을 허용하지
않는다. 배열 필드는 값이 없어도 생략하거나 `null`로 저장하지 않고 빈 배열 `[]`을
저장한다. `chunk_index`는 문서마다 0부터 시작한다.

### `source_file_name`

현재 문서 집합에서는 파일명이 유일하고 변경되지 않으므로 문서 그룹 키로 사용한다.
특정 상품 문서를 선택한 뒤 더 깊게 검색할 때 모든 vector query에 정확한
`source_file_name` 필터를 적용한다.

파일명은 표시값이면서 현재의 문서 식별자다. 파일명이 자연어 질의와 일치한다고
가정하지 않는다. 상품 탐색 결과나 UI 선택 결과에서 저장된 정확한 파일명을 얻은 뒤
필터에 전달한다.

### `source_format`

초기 허용값은 `pdf`, `docx`, `pptx`, `xlsx`다. 소문자 확장자 기준으로 저장한다.
새 형식을 지원할 때 허용값과 위치 표시 규칙을 함께 추가한다.

### `document_type`

`document_type`은 Docling이나 LLM이 본문을 보고 추론하지 않는다. 입력 폴더와
파일명처럼 재현 가능한 ingest 규칙으로 지정한다.

초기 허용값은 다음과 같다.

| 값 | 의미 |
| --- | --- |
| `investment_prospectus` | 투자설명서 |
| `summary_investment_prospectus` | 간이투자설명서 |
| `product_document` | 상품 안내와 상품 관련 부속 문서 |
| `reference_document` | 일반 참고 문서 |
| `unknown` | 정해진 규칙으로 분류할 수 없는 문서 |

분류할 수 없는 문서를 임의로 가장 가까운 유형에 넣지 않고 `unknown`으로 저장한다.
후속 ingest 구현은 적용한 분류 규칙을 테스트로 고정한다.

### `chunk_index`

같은 `source_file_name` 안에서 0부터 증가하는 청크 순서다. vector 유사도 점수나
검색 순위를 뜻하지 않는다. 검색 결과 앞뒤의 청크를 가져오거나 문서 순서를 복원할
때만 사용한다.

### `content`와 `embedding_content`

두 본문은 용도를 분리한다.

- `content`: `DocChunk.text`에 해당하는 인용용 청크 직렬화 결과다. 검색 결과와
  최종 근거에는 이 값을 사용한다.
- `embedding_content`: `chunker.contextualize(chunk)` 결과다. 제목 계층, 캡션과
  반복된 표 헤더처럼 검색 문맥을 위한 문자열이 포함될 수 있으며 dense와 sparse
  vector 생성에는 이 값을 사용한다.

`embedding_content`에 추가된 제목이나 반복 표 헤더를 원문 본문인 것처럼 인용하지
않는다. 평가 API의 근거 본문에는 항상 `content`만 전달한다.

### `heading_path`

문서의 가장 큰 상위 제목부터 현재 청크에 가장 가까운 제목 순서로 저장한다.

```json
[
  "제2부 집합투자기구에 관한 사항",
  "투자위험",
  "시장위험"
]
```

단일 `title`을 payload에 저장하지 않는다. `heading_path`는 제목 계층을 보존하고
마지막 원소로 `title`을 만들 수 있지만, 단일 `title`에서는 상위 계층을 복원할 수
없기 때문이다.

제목이 자연어 검색에 사용되도록 `embedding_content`에 포함한다. 동일한 제목을
정확히 필터링하는 기능이 실제로 필요해질 때만 `section_title`을 별도 keyword
필드로 추가한다.

### `captions`

청크에 연결된 표와 그림의 캡션을 문서 순서대로 저장한다. 캡션이 없으면 `[]`이다.
캡션은 임베딩 문맥과 근거 설명에 사용할 수 있지만 초기 payload index는 만들지
않는다.

### `element_types`

HybridChunker의 한 청크에는 여러 document item이 포함될 수 있으므로 단일
`element_type`이 아니라 중복을 제거한 배열로 저장한다. 배열 순서는 청크에 처음
나타난 document item 순서를 따른다.

초기 허용값은 다음과 같다.

```text
title
section_header
text
list_item
table
picture
caption
formula
code
unknown
```

새 Docling label을 매핑하지 못하면 값을 버리거나 추측하지 않고 `unknown`을
포함한다. 표 전용 검색에서는 `element_types` 배열에 `table`이 포함된 청크만
검색한다.

### `page_numbers`

청크에 포함된 모든 document item의 `prov.page_no`를 모아 중복을 제거하고 오름차순
정렬한 배열이다. 페이지 번호는 1부터 시작한다.

```python
page_numbers = sorted(
    {provenance.page_no for item in chunk.meta.doc_items for provenance in item.prov}
)
```

단일 페이지 청크도 `[12]`처럼 배열로 저장한다. 여러 페이지에 걸친 청크는
`[12, 13]`, 고정 페이지 정보를 제공하지 않는 문서는 `[]`로 저장한다. 특히 DOCX는
원본 형식에 고정 페이지가 없으므로 빈 배열을 정상값으로 취급한다.

`page`, `page_start`, `page_end`와 `locator`는 중복 저장하지 않는다.

## Docling 매핑

| Payload 필드 | Docling 또는 ingest 값 |
| --- | --- |
| `source_file_name` | parser manifest의 원본 파일명 |
| `source_format` | parser manifest의 원본 확장자 |
| `document_type` | ingest 경로·파일명 분류 규칙 |
| `chunk_index` | `chunker.chunk()` 결과의 0 기반 열거 순서 |
| `content` | `DocChunk.text` |
| `embedding_content` | `chunker.contextualize(chunk)` |
| `heading_path` | `DocChunk.meta.headings` 또는 `[]` |
| `captions` | `DocChunk.meta.captions` 또는 `[]` |
| `element_types` | `DocChunk.meta.doc_items[*].label`의 정규화 결과 |
| `page_numbers` | `DocChunk.meta.doc_items[*].prov[*].page_no`의 정렬된 집합 |

파싱 단계의 `document.docling.json`은 구조 보존과 품질 검수의 원본으로 계속
보관한다. 그러나 현재 검색 계층은 Docling JSON의 특정 item을 다시 조회하지 않으므로
`doc_item_refs`는 Qdrant payload에 저장하지 않는다.

## 파생 응답 필드

평가 API가 사용하는 `chunk_id`, `title`과 `locator`는 Qdrant 조회 결과에서 만든다.

### `chunk_id`

Qdrant Point ID를 문자열로 변환한다.

```python
chunk_id = str(point.id)
```

### `title`

비어 있지 않은 `heading_path`의 마지막 값을 사용한다. 제목 계층이 없으면 파일명의
마지막 확장자를 제거한 값을 사용한다.

```python
title = heading_path[-1] if heading_path else source_file_name.rsplit(".", 1)[0]
```

### `locator`

페이지가 있으면 사람이 확인할 수 있는 페이지 문자열을 만든다. 페이지가 없으면
제목을 사용하고, 제목도 없으면 0 기반 `chunk_index`를 사람이 읽는 1 기반 순서로
변환한다. 평가 API의 `locator`는 필수 문자열이므로 빈 값이나 `None`을 반환하지
않는다.

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

### 평가 API 매핑

`EvidenceChunkResponse`에는 검색 후 실제 답변 근거로 선택된 청크만 변환한다.

| API 필드 | Qdrant 조회 결과 |
| --- | --- |
| `chunk_id` | `str(point.id)` |
| `source_file_name` | `payload.source_file_name` |
| `title` | `heading_path` 또는 파일명에서 파생 |
| `locator` | `page_numbers`, `heading_path`, `chunk_index`에서 파생 |
| `content` | `payload.content` |

`embedding_content`와 내부 filter metadata는 평가 API 응답에 노출하지 않는다.

## Payload index

초기 collection에는 실제 filter와 범위 조회에 사용하는 네 필드만 payload index로
만든다. filterable HNSW가 적재 단계부터 이 index를 활용할 수 있도록 대량 적재 전에
생성한다.

| 필드 | Index type | 사용하는 조회 |
| --- | --- | --- |
| `source_file_name` | `keyword` | 특정 파일 내부 검색 |
| `document_type` | `keyword` | 문서 종류 제한 |
| `element_types` | `keyword` | 표·그림·텍스트 등 요소 제한 |
| `chunk_index` | `integer` | 같은 파일의 인접 청크 범위 조회 |

다음 필드에는 초기 payload index를 만들지 않는다.

```text
source_format
content
embedding_content
heading_path
captions
page_numbers
```

저장하는 것과 index를 만드는 것은 별개의 결정이다. 이후 실제 query에서 filter로
사용하는 필드가 추가될 때 query 패턴과 cardinality를 확인한 후 index를 추가한다.

## 검색 접근 계약

후속 Qdrant Repository는 Qdrant SDK 타입을 상위 `agent` 또는 `api` 모듈에 노출하지
않고 `pension_agent/retrieval/` 안에서 변환한다. `api`는 프로젝트 의존성 규칙에 따라
`retrieval`을 직접 호출하지 않는다.

Embedding 경계는 사용자 질의를 dense vector로 변환하고, Qdrant BM25 생성에 사용할
원문 질의와 함께 Repository에 전달한다.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class HybridQuery:
    text: str
    dense: list[float]
```

Qdrant SDK 타입이 공용 계약으로 새지 않도록 프로젝트 타입을 `core`에 두고,
`retrieval` 구현 안에서 `text`를 `models.Document`로 변환한다. 이 계약은 호출자가
Qdrant의 sparse vector index와 value를 직접 만들 필요가 없게 한다.

### 공통 검색

```python
search_chunks(
    query: HybridQuery,
    *,
    source_file_name: str | None = None,
    document_type: str | None = None,
    element_types: list[str] | None = None,
    limit: int = 10,
) -> list[SearchHit]
```

- `dense`와 `sparse`를 각각 같은 payload filter로 prefetch한다.
- 각 prefetch 결과는 최종 `limit`보다 넓게 가져오고 RRF로 결합한다.
- 지정된 payload filter를 각 prefetch의 `must` 조건으로 결합한다.
- `element_types`가 여러 개면 하나 이상을 포함하는 청크를 허용한다.
- RRF 결합 점수 내림차순으로 반환한다.
- payload 누락이나 잘못된 자료형은 조용히 보정하지 않고 retrieval 경계의 데이터
  오류로 처리한다.

```python
client.query_points(
    collection_name="pension_documents",
    prefetch=[
        models.Prefetch(
            query=models.Document(
                text=query.text,
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

초기값은 각 검색에서 30개를 prefetch하고 RRF 결과 10개를 반환한다. 이 값은 계약이
아니며 검색 평가셋의 recall과 precision을 근거로 조정한다.

### 특정 문서 내부 검색

```python
search_within_document(
    query: HybridQuery,
    *,
    source_file_name: str,
    document_type: str | None = None,
    element_types: list[str] | None = None,
    limit: int = 10,
) -> list[SearchHit]
```

상품 탐색 또는 사용자 선택으로 확정된 정확한 `source_file_name`을 필수 filter로
적용한다. 해당 상품을 더 깊게 조사하는 기본 검색 경로다.

### 인접 청크 조회

```python
get_neighbor_chunks(
    *,
    source_file_name: str,
    chunk_index: int,
    before: int = 1,
    after: int = 1,
) -> list[Chunk]
```

`source_file_name`이 같은 Point 중 다음 범위를 조회한다.

```text
chunk_index - before <= payload.chunk_index <= chunk_index + after
```

결과는 유사도 점수가 아니라 `chunk_index` 오름차순으로 정렬한다. 범위를 문서
처음과 끝에 맞게 자르고 음수 index를 요청하지 않는다.

### 단건 조회

```python
get_chunk(chunk_id: str) -> Chunk | None
```

문자열 UUID를 Qdrant Point ID로 검증한 후 조회한다. 존재하지 않는 ID는 `None`,
잘못된 UUID는 입력 오류로 구분한다.

## 현재 제외하는 필드

| 제외 필드 | 제외 이유 | 추가하는 시점 |
| --- | --- | --- |
| `product_id` | 현재 상품 문서를 파일명으로 유일하게 선택할 수 있음 | 한 상품에 여러 문서를 묶어 검색할 때 |
| `document_id` | 파일명이 유일하고 변경되지 않음 | 문서 registry를 만들거나 파일명이 변경될 때 |
| `document_version_id` | 공모전 중 문서 개정이 없다고 가정함 | 같은 문서의 여러 버전을 함께 보관할 때 |
| `source_hash` | 원본 해시는 parser manifest에 이미 존재함 | Qdrant만으로 원본 무결성을 검사할 때 |
| `content_hash` | 증분 재임베딩과 청크 중복 제거를 하지 않음 | 변경된 청크만 다시 임베딩할 때 |
| `chunking_version` | 모든 Point가 같은 적재 작업의 청킹 설정을 사용함 | payload가 아니라 retrieval build manifest에서 관리 |
| `corpus` | 현재 검색 범위는 `document_type`으로 충분함 | 수집 출처 자체를 독립적으로 filter할 때 |
| `title` | `heading_path`에서 파생 가능함 | 저장이 아니라 응답 변환에서 생성 |
| `section_title` | 정확한 제목 filter 요구가 아직 없음 | 같은 소제목의 청크만 정확히 filter할 때 |
| `locator` | 페이지·제목·순서에서 파생 가능함 | 저장하지 않고 응답 변환에서 생성 |
| `page_start`, `page_end` | `page_numbers`에서 파생 가능함 | 페이지 범위 filter가 실제로 필요할 때 |
| `doc_item_refs` | Docling JSON item 재조회 기능이 없음 | 표 구조 복원이나 bbox 하이라이트 기능을 만들 때 |
| `token_count` | 검색 filter나 응답에서 소비하지 않음 | Qdrant가 아니라 청킹 품질 산출물에서 관리 |
| `domains`, `section_key` | 신뢰할 수 있는 자동 추출 규칙이 없음 | 별도 분류 정책과 평가 기준이 생길 때 |

## 재검토 조건

다음 중 하나라도 발생하면 이 계약을 변경하는 별도 결정과 migration 계획을 먼저
작성한다.

- 같은 상품에 속한 여러 문서를 한 번에 검색해야 한다.
- 파일명이 바뀌거나 같은 이름의 다른 파일이 유입된다.
- 원본 문서가 개정되고 구버전과 신버전을 함께 보관한다.
- 변경된 청크만 다시 임베딩하는 증분 적재가 필요하다.
- Docling JSON에서 표, 그림 또는 bounding box를 다시 가져온다.
- 제목이나 페이지 범위를 정확한 payload filter로 검색한다.

## 관련 자료

- [로컬 Qdrant 실행과 확인](operations/qdrant-local.md)
- [문서 파싱 운영](operations/document-parsing.md)
- [Qdrant payload](https://qdrant.tech/documentation/concepts/payload/)
- [Qdrant indexing](https://qdrant.tech/documentation/manage-data/indexing/)
- [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)
- [Qdrant BM25](https://qdrant.tech/documentation/inference/inference-bm25/)
- [CLOVA Studio 임베딩](https://guide.ncloud-docs.com/docs/ko/clovastudio-explorer03)
- [BAAI BGE-M3](https://huggingface.co/BAAI/bge-m3)
- [Docling chunking](https://docling-project.github.io/docling/concepts/chunking/)
- [GitHub 이슈 #33](https://github.com/nayeon653/-ace3/issues/33)
