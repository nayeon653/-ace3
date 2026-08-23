# 평가용 API 명세

주최측이 평가기간(2026-09-07 ~ 09-20) 중 GET으로 호출할 API 명세다.
배포 호스트는 배포 후 확정하며 경로와 응답 계약은 아래와 같이 고정한다.

## Endpoint

```
GET {TBD}/answer
```

### 요청 파라미터

| 이름 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `question_id` | string | Y | 질의 고유 ID (주최측 평가셋 기준) |
| `question` | string | Y | 자연어 질의 |

### 응답 (200)

정확히 아래 5개 필드만 포함한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `question_id` | string | 요청받은 `question_id` 그대로 반환 |
| `question` | string | 요청받은 `question` 그대로 반환 |
| `retrieved_context` | array[object] | 실제로 답변에 인용된 근거 문서 목록 (리랭킹/컷오프 후) |
| `think_trace` | string | 조건 분기 판단 과정 요약 |
| `answer` | string | 최종 답변. 확인이 필요한 조건과 조건별 결론을 포함할 수 있음 |

`retrieved_context`의 각 객체는 아래 필드를 포함한다. 완료된 도메인 판단 중
`decision.status`가 `not_applicable`이 아닌 결과에서 최종 답변에 실제 사용한
근거만 포함한다. 상품 카탈로그 개수·목록 조회는 Qdrant 청크 대신 검증된
`product_catalog.json` 조회 결과를 하나의 결정론적 근거로 포함하며, `content`에
조회 route, 공식 운용사 조건, 정확한 개수·목록과 `catalog_version`을 기록한다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `chunk_id` | string | 근거 청크 식별자 |
| `source_file_name` | string | 출처 문서 파일명 |
| `title` | string | 근거 구간 제목 |
| `locator` | string | 원문에서 근거 위치를 찾기 위한 표시 |
| `content` | string | 답변에 실제 사용한 근거 본문 |

`think_trace`는 실제 도메인 호출·실행 상태, 판단 결론과 누락 조건을 서버가
결정론적으로 요약한 문장이다. LLM 내부 사고 과정, 원시 Tool 로그, 원시 예외,
stack trace, 내부 경로와 모델 내부 메시지는 포함하지 않는다. 카탈로그 조회에서는
검증된 route, 운용사, 반환 방식, 상품 개수와 카탈로그 버전을 요약하고 전체 상품
목록은 반복하지 않는다.

```json
{
  "question_id": "Q-001",
  "question": "연금계좌를 이전할 수 있나요?",
  "retrieved_context": [
    {
      "chunk_id": "CH-001",
      "source_file_name": "policy.pdf",
      "title": "연금계좌 업무 지침",
      "locator": "3쪽",
      "content": "가입 유형에 따라 이전 범위가 달라집니다."
    }
  ],
  "think_trace": "도메인 호출: policy(완료). 판단 요약: policy=조건부: 가입 유형에 따라 이전할 수 있습니다. 확인이 필요한 조건: policy=가입 유형.",
  "answer": "가입 유형을 확인한 뒤 이전 가능 여부를 판단하세요."
}
```

### 에러 응답

| 상태 코드 | 상황 |
|---|---|
| 400 | 필수 파라미터 누락, 빈 값 등 입력 오류 |
| 500 | 의존성 초기화, 근거 검색, Agent 실행이나 응답 조립 오류 |
| 503 | 프로세스의 활성 4개와 대기 64개 answer admission이 모두 사용 중인 경우 |

오류 응답은 원시 입력 검증 내용이나 내부 실행 정보를 노출하지 않고 다음 형태로
반환한다.

```json
{
  "detail": "요청 파라미터가 올바르지 않습니다."
}
```

## Health Check

```
GET {TBD}/health
```

평가기간 중 서버 생존 여부를 확인하기 위한 엔드포인트. 커밋 SHA를 포함해
현재 배포 버전을 추적할 수 있게 한다.

```json
{
  "status": "ok",
  "commit_sha": "abc123def456"
}
```

`/health`는 LLM과 검색 시스템을 호출하지 않는다. `commit_sha`는 배포 환경의
`DEPLOY_COMMIT_SHA` 값이며, 로컬에서 주입하지 않으면 `unknown`을 반환한다. 운영
배포에서는 이미지나 릴리스를 만든 정확한 Git 커밋 SHA를 반드시 주입한다.

FastAPI lifespan은 서버 시작 시 HCX-005, bge-m3, Qdrant, 결정론적 `SearchService`,
Domain Agent 3종, Main Supervisor와 `AnswerService`를 프로세스당 한 번 조립한다.
`/answer` 요청은 조립된 동일 객체를 재사용하며 요청별
상태는 공유하지 않는다. 필수 인증·연결 설정이 없거나 조립에 실패하면 서버 시작이
실패한다. `/health` 요청 자체는 조립된 Agent를 실행하지 않는다.

제품 실행 경로는 FastAPI부터 HCX, query embedding과 Qdrant까지 native async를
사용한다. `/answer` capacity 대기부터 최종 응답 조립까지 기본 180초의 하나의 deadline을
적용하며, 프로세스당 활성 답변 4개, 대기 답변 64개와 provider별 동시성 상한을 둔다.
admission 68개를 넘는 요청은 Agent를 시작하지 않고 정제된 503을 반환한다. 연결이 먼저
끊기면 ASGI disconnect를 감지해 하위 answer coroutine을 취소한다. 따라서 provider를
기다리는 요청이 있어도 `/health`는 같은 event loop에서 독립적으로 응답한다. 구체적인
상한과 Uvicorn worker 수에 따른 배수는
[`API 서버 실행과 확인`](operations/api-server.md)의 비동기 실행 예산을 따른다.

서버 실행, 환경변수, 로컬 확인과 배포 방법은
[`API 서버 실행과 확인`](operations/api-server.md)을 따른다.
