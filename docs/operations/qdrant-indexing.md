# Qdrant 인덱싱 실행

검증된 통합 청크를 NAVER CLOVA Studio `bge-m3`로 임베딩하고 Qdrant Cloud에
dense+sparse hybrid Point로 적재하는 절차다. 저장 구조는
[Qdrant collection·payload 명세](../retrieval/qdrant-index-spec.md)를 따른다.

## 입력과 출력

기본 경로는 모두 Git에서 제외된다.

```text
data/indexes/pension_documents_v1/
├── input/
│   ├── chunks.jsonl
│   ├── knowledge_sources.jsonl
│   └── prospectus_sources.jsonl
├── embedding_cache.sqlite3
└── manifest.json
```

- `chunks.jsonl`: 두 문서군을 합친 canonical 청크
- `*_sources.jsonl`: `source_id`와 원본 파일·canonical 문서를 연결하는 manifest
- `embedding_cache.sqlite3`: Point ID·모델·본문 해시별 float32 dense vector cache
- `manifest.json`: 전체 적재와 Point 수 확인이 끝난 경우에만 기록하는 build manifest

현재 기준 입력은 source 158개, canonical 문서 149개, 청크 19,747개다.

## 환경변수

저장소 루트의 `.env`에 다음 값을 둔다. 실제 API key는 출력하거나 Git에 커밋하지 않는다.

```dotenv
CLOVASTUDIO_API_KEY=...
CLOVASTUDIO_API_BASE_URL=https://clovastudio.stream.ntruss.com/v1/openai

QDRANT_URL=https://<cluster>.<region>.<provider>.cloud.qdrant.io
QDRANT_API_KEY=...
QDRANT_COLLECTION=pension_documents_v1
```

`QDRANT_CLOUD_INFERENCE`는 보통 생략한다. URL이 `*.cloud.qdrant.io`이면 Qdrant의
server-side `qdrant/bm25` 변환을 자동으로 활성화한다. 로컬에서 Cloud inference API를
대체할 수 있는 구성이 따로 있을 때만 명시적으로 설정한다.

## 1. 외부 호출 없는 입력 검증

```bash
make qdrant-index-validate
```

JSONL schema, 본문 SHA-256, 중복 ID, source manifest 참조, canonical 문서 집합과 문서별
청크 순서를 전체 검사한다. 성공 결과의 count가 예상 입력과 같은지 확인한다.

## 2. Qdrant 연결 확인

```bash
make qdrant-check
```

`.env`의 endpoint에 `/readyz` 요청을 보내고 SDK로 collection 목록을 읽는다. 이 단계는
collection이나 Point를 변경하지 않고 CLOVA API도 호출하지 않는다.

## 3. 1건 샘플 적재

```bash
uv run --frozen --env-file .env python infra/index_qdrant.py load \
  --limit 1 \
  --batch-size 1
```

collection이 없으면 `dense` 1,024차원 cosine, `sparse` IDF와 세 payload index를 만든 뒤
1건만 임베딩하고 upsert한다. 결과가 `"status": "partial"`, `processed: 1`이면 정상이다.
같은 명령을 다시 실행했을 때 `embedded: 0`, `cache_hits: 1`이면 재시작 cache까지
검증된 것이다.

기존 collection의 vector 이름·차원·거리·sparse modifier 또는 payload index 형식이
다르면 자동 삭제하거나 덮어쓰지 않고 실패한다.

## 4. 전체 적재

전체 임베딩 비용과 실행 시간을 확인하고 승인한 뒤에만 `--limit` 없이 실행한다.

```bash
uv run --frozen --env-file .env python infra/index_qdrant.py load \
  --batch-size 16 \
  --embedding-workers 4 \
  --requests-per-minute 55
```

`batch-size`는 cache 확인과 Qdrant upsert 단위다. CLOVA Embeddings API의 현재 단일 문자열
입력 계약 때문에 실제 dense 임베딩 요청 수는 cache miss 청크 수와 같다. 독립 요청은
`embedding-workers` 수만큼 제한적으로 병렬 실행하되 테스트 앱의 QPM 제한을 넘지 않도록
요청 시작을 `requests-per-minute`로 조절한다. 완전히 같은 `embedding_content`는 vector를
재사용한다. 현재 corpus의 고유 입력은 15,371개이므로 최초 전체 실행의 최대 API 호출도
15,371회다.

터미널 종료, 네트워크 오류나 rate limit으로 중단되면 같은 명령을 다시 실행한다. 이미
성공한 dense vector는 SQLite cache에서 읽고, 결정적 UUID로 같은 Point를 upsert한다.
cache 파일을 삭제하면 완료된 임베딩도 다시 호출하므로 적재가 끝날 때까지 보존한다.

전체 실행은 마지막에 Qdrant의 정확한 Point 수가 입력 청크 수와 같은지 확인한다.
일치할 때만 `manifest.json`을 기록하고 `"status": "complete"`를 출력한다. 기존에 다른
입력의 Point가 섞여 있어 count가 다르면 실패하므로 별도 version collection을 사용한다.

## 비용과 운영 주의

- Qdrant 무료 cluster 사용료와 CLOVA 임베딩 API 비용은 별개다. Point를 그대로 두는
  것보다 최초 전체 임베딩 호출이 비용의 핵심이다.
- `validate`와 `qdrant-check`는 CLOVA 비용이 없고, `load --limit 1`은 cache가 없을 때
  1건만 임베딩한다.
- 제출일까지 cluster를 유지할 경우 Qdrant Cloud 콘솔의 free tier 상태와 일시 중지·삭제
  정책을 확인한다. 유료 전환 또는 리소스 상향은 별도 승인 후 진행한다.
- API key와 endpoint는 `.env` 또는 배포 secret에만 두고 로그·이슈·커밋에 남기지 않는다.

## 구현 위치

- 실행 CLI: [`infra/index_qdrant.py`](../../infra/index_qdrant.py)
- 입력 검증·변환: [`pension_agent/ingest/qdrant_input.py`](../../pension_agent/ingest/qdrant_input.py)
- cache·collection·upsert: [`pension_agent/ingest/qdrant_indexer.py`](../../pension_agent/ingest/qdrant_indexer.py)
- CLOVA embedding adapter: [`pension_agent/retrieval/clova_embedder.py`](../../pension_agent/retrieval/clova_embedder.py)
