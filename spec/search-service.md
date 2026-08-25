# Search Service 스펙

## 지위와 책임

Search Service는 Domain Agent가 사용하는 결정론적 검색 컴포넌트다. LLM을 호출하지 않고
입력 힌트에 따라 검색 경로를 한 번 선택하며, 권한과 provenance를 재검증한 원문 청크만
반환한다.

자연어 답변, 제도·세제·상품 결론, 확정 계산과 근거 충분성 판단은 수행하지 않는다.

## 요청과 권한

`SearchRequest`는 다음 필드만 허용한다.

| 필드 | 설명 |
|---|---|
| `objective` | 비어 있지 않은 하나의 근거 검색 목표 |
| `source_file_name` | 신뢰 가능한 원본 파일명 힌트 |
| `chunk_id` | 신뢰 가능한 UUID 청크 ID |
| `expand_neighbors` | 기준 청크의 앞뒤 구조 문맥 확장 여부 |

`source_file_name`과 `chunk_id`는 동시에 사용할 수 없다. Domain 권한은 모델 입력이 아니라
신뢰된 Tool 경계에서 주입한다.

| 권한 | 허용 문서 유형 |
|---|---|
| `policy` | `pension_reference` |
| `tax_payout` | `pension_reference` |
| `product` | `fund_prospectus` |

## Router

같은 요청과 설정은 같은 최초 계획을 만든다.

| 우선순위 | 조건 | route | embedding |
|---:|---|---|---|
| 1 | `chunk_id` 있음 | `chunk_lookup` | 사용하지 않음 |
| 2 | `source_file_name` 있음 | `within_document` | `bge-m3` |
| 3 | 힌트 없음 | `global` | `bge-m3` |

문서 검색 기본 모드는 Hybrid다. 최초 검색은 한 번만 실행하며 `expand_neighbors=true`일 때
권한 검증된 최상위 anchor를 기준으로 인접 조회를 최대 한 번 추가한다.

## 필터와 결과

기본 설정은 후보 10개, 최종 5개, 앞뒤 인접 청크 각 1개, score cutoff 비활성화다.
EvidenceFilter는 점수 안정 순서, UUID 중복 제거, 탐색 전용 목차·질문 목록 제거와 결과 수
제한을 적용한다. 직접·인접 조회는 문서 순서와 anchor를 보존한다.

`SearchResult`는 다음 필드를 가진다.

- `execution_status`: `completed`, `failed`, `timeout`
- `retrieved_chunks`: 검증된 원문 청크 목록
- `limitations`: 완료했지만 확인하지 못한 범위
- `error`: 실패 또는 timeout의 정제 오류

완료 결과는 청크가 없을 수 있다. 실패와 timeout에는 청크를 포함하지 않는다. Search
Service가 충분성 상태를 만들지 않고, Domain Agent가 빈 결과를 `undetermined` 판단으로
변환한다.

## 실행 제한

| 제한 | 값 |
|---|---:|
| 실행 deadline | 45초 또는 상위 deadline 중 빠른 시각 |
| 동시 Search Service 실행 | 프로세스당 4개 |
| 동시 embedding/Qdrant | 각각 프로세스당 4개 |

원시 Provider·Qdrant 예외, 인증 정보와 내부 주소는 결과에 포함하지 않는다.

## 검증 위치

- `tests/unit/agent/search/`
- `tests/unit/agent/test_search_schemas.py`
- `tests/integration/test_qdrant_agent_vertical.py`
