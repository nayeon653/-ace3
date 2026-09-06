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

`application/json`으로 반환하며, 정확히 아래 5개 필드만 포함한다. 모든 필드의 값은
문자열(`string`)이다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `question_id` | string | 요청받은 `question_id` 그대로 반환 |
| `question` | string | 요청받은 `question` 그대로 반환 |
| `retrieved_context` | string | 실제로 답변에 인용된 근거 문서를 순서대로 연결한 문자열 (리랭킹/컷오프 후) |
| `think_trace` | string | 조건 분기 판단 과정 요약 |
| `answer` | string | 최종 답변. 확인이 필요한 조건과 조건별 결론을 포함할 수 있음 |

`retrieved_context`는 아래 형식의 문서 블록을 빈 줄(`\n\n`)로 연결한 문자열이다.
문서 번호는 1부터 순서대로 붙이고, 선택된 근거의 순서와 메타데이터·본문을 그대로
보존한다. 본문에 포함된 줄바꿈도 보존하며, 근거가 없으면 빈 문자열(`""`)을 반환한다.

```text
[문서 1]
chunk_id: CH-001
source_file_name: policy.pdf
title: 연금계좌 업무 지침
locator: 3쪽
content:
가입 유형에 따라 이전 범위가 달라집니다.
```

각 블록에는 근거 청크 식별자(`chunk_id`), 출처 문서 파일명(`source_file_name`), 근거
구간 제목(`title`), 원문 위치(`locator`), 답변에 실제 사용한 본문(`content`)을 위 순서로
기록한다.

완료된 도메인 판단 중
`decision.status`가 `not_applicable`이 아닌 결과에서 최종 답변에 실제 사용한
근거만 포함한다. 단, 도구가 완료한 `comparison_answer`의 선택 근거는 모델 판단 상태와
관계없이 포함한다. 상품 카탈로그 개수·목록 조회는 Qdrant 청크 대신 검증된
`product_catalog.json` 조회 결과를 하나의 결정론적 근거로 포함하며, `content`에
조회 route, 공식 운용사 조건, 정확한 개수·목록과 `catalog_version`을 기록한다.
상품 비교에서는 비교 생성기가 사용했다고 선택한 ID 중 실제 검색 결과에 존재하는 청크만
포함한다. 존재하지 않는 ID는 제외하며, 본문과 인용의 의미를 자동 검증하지 않는다.
같은 문서 alias를 공유하는 상품의 중복 청크도 ID 기준으로 한 번만 들어간다.

`think_trace`는 실제 도메인 호출·실행 상태, 판단 결론과 누락 조건을 서버가
결정론적으로 요약한 문장이다. LLM 내부 사고 과정, 원시 Tool 로그, 원시 예외,
stack trace, 내부 경로와 모델 내부 메시지는 포함하지 않는다. 카탈로그 조회에서는
검증된 route, 운용사, 반환 방식, 상품 개수와 카탈로그 버전을 요약하고 전체 상품
목록은 반복하지 않는다.
비교 응답은 `상품 비교 응답 준비 완료`로 요약한다. 비교 도구의 답안뿐 아니라 검색 근거나
식별 대상이 부족해 Python이 안내를 만든 경우도 포함하며, 도구나 작성 모델이 실제 실행됐다는
뜻은 아니다. HTTP 200이나 응답 준비 완료는 문장·인용의 정확성이나 요청 충족을 보증하지 않는다.

상품 비교의 `answer`는 `compare_products`가 완료한 본문과 조건·경고를 보존한다.
Python이 청크별 출처 목록을 답변 끝에 추가하지 않으며, 작성 모델은 본문에 문서명·위치를
짧게 표시하도록 지시받는다. 선택된 근거는 `retrieved_context`에 보존한다.
Product나 Main이 새로 작성한 비교 문장은 채택하지 않는다. 검색 근거가 없으면
정해진 판단 불가 안내를 반환하고, 식별 부족이면 대상과 이유를 담은 간단한 안내를 사용한다.
내부 `comparison_answer`는 별도의 외부 필드로 노출하지 않으며
위의 정확한 5개 필드를 유지한다.

```json
{
  "question_id": "Q-001",
  "question": "연금계좌를 이전할 수 있나요?",
  "retrieved_context": "[문서 1]\nchunk_id: CH-001\nsource_file_name: policy.pdf\ntitle: 연금계좌 업무 지침\nlocator: 3쪽\ncontent:\n가입 유형에 따라 이전 범위가 달라집니다.",
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

Domain의 `failed`·`timeout`을 검증된 결과값으로 처리하고 응답 조립까지 완료한 요청은
HTTP 200일 수 있다. 하나 이상의 Domain이 실패하거나 timeout이면 완료한 Domain의
가용 결론·조건·경고와 기존 계산·숫자 처리 결과, 실패한 Domain의 정제된 오류를 함께
결정론적으로 조립한다. 호출한 모든 Domain이 실패하면 정제된 실패 안내만 반환한다.
어느 경우에도 실패한 판단을 Main의 근거 없는 일반론으로 대신하지 않는다.
위의 500은 요청 실행 또는 조립 경계에서 정상 결과로 변환하지 못한 오류를 뜻한다.

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

FastAPI lifespan은 서버 시작 시 역할별 HCX-007 비추론 모델, bge-m3, Qdrant, 결정론적
`SearchService`, Domain Agent 3종, Main Supervisor와 `AnswerService`를 프로세스당 한 번
조립한다.
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
[`API 서버 실행과 확인`](../operations/api-server.md)의 비동기 실행 예산을 따른다.

서버 실행, 환경변수, 로컬 확인과 배포 방법은
[`API 서버 실행과 확인`](../operations/api-server.md)을 따른다.
