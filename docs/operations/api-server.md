# API 서버 실행과 확인

FastAPI 서버를 로컬에서 실행하고 동작을 확인하는 방법과 배포 환경의 차이를 정리한다.
외부 요청·응답 필드 계약은 [`docs/api-spec.md`](../api-spec.md)를 따른다.

## 최초 준비

저장소 루트에서 개발 의존성을 설치하고 로컬 환경 파일을 만든다.

```bash
uv sync --dev
cp .env.example .env
```

`.env`에서 `CLOVASTUDIO_API_KEY`와 Qdrant 연결을 설정한다. 키를 문서, 로그,
커밋이나 채팅에 남기지 않는다. 로컬 Qdrant를 사용하면 먼저 `make qdrant-up`과
적재 파이프라인으로 `QDRANT_COLLECTION`에 지정한 collection을 준비한다.

```dotenv
CLOVASTUDIO_API_KEY=<발급받은 실제 API 키>
CLOVASTUDIO_API_BASE_URL=https://clovastudio.stream.ntruss.com/v1/openai
QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=pension_documents_v1
```

`.env.example`을 복사했다면 `CLOVASTUDIO_API_BASE_URL`에는 기본 주소가 이미 있으므로
일반적인 로컬 실행에서는 수정하지 않는다. 서버는 시작할 때 Agent 객체를 조립하므로
필수 연결 설정이 없으면 시작하지 않는다.

## 가장 간단한 로컬 실행

일반적인 로컬 테스트는 다음 한 줄이면 충분하다.

```bash
uv run uvicorn pension_agent.api.app:app --env-file .env
```

Uvicorn 기본값에 따라 `127.0.0.1:8000`에서 실행된다. 로컬에서는 배포 버전 추적이
필수가 아니므로 `DEPLOY_COMMIT_SHA`를 생략할 수 있다. 생략하면 `/health`의
`commit_sha`는 `unknown`이다.

`--env-file .env`는 `.env`의 값을 Uvicorn이 실행하는 애플리케이션 프로세스의
환경변수로 주입한다. `ClovaStudioConnection`은 Pydantic Settings를 통해 `.env`를
직접 읽지만, LangSmith 기본 tracing은 프로세스 환경의 `LANGSMITH_*`를 읽으므로
LangSmith를 활성화한 로컬 실행에는 이 옵션이 필요하다.

코드 변경 시 서버를 자동 재시작하려면 다음과 같이 실행한다.

```bash
uv run uvicorn pension_agent.api.app:app --env-file .env --reload
```

자동 재시작 때마다 서버 프로세스와 Agent 객체가 새로 생성된다.

## 옵션을 명시하는 로컬 실행

바인딩 주소, 포트와 현재 커밋을 명시해서 확인하려면 다음 명령을 사용한다.

```bash
DEPLOY_COMMIT_SHA="$(git rev-parse HEAD)" \
uv run uvicorn pension_agent.api.app:app \
  --env-file .env \
  --host 127.0.0.1 \
  --port 8000
```

`127.0.0.1`은 현재 컴퓨터 안에서만 접속을 허용한다. 로컬 테스트에서는 이 주소를
기본으로 사용한다.

## 동작 확인

서버가 시작되면 별도 터미널에서 상태를 확인한다.

```bash
curl http://127.0.0.1:8000/health
```

Swagger UI와 OpenAPI 문서는 다음 주소에서 확인할 수 있다.

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>

`/answer`는 쿼리 문자열을 직접 조립하지 않고 `curl --data-urlencode`로 호출하면 한글과
공백을 안전하게 인코딩할 수 있다.

```bash
curl --get http://127.0.0.1:8000/answer \
  --data-urlencode 'question_id=Q-001' \
  --data-urlencode 'question=연금계좌를 이전할 수 있나요?'
```

이 요청은 실제 HCX API를 호출할 수 있다. 개발자가 개인 로컬 `.env`에서
`LANGSMITH_TRACING=true`로 설정했다면 LangChain 기본 연동이 질문, Supervisor state,
Tool 입출력과 최종 답변을 개인 LangSmith project에 기록한다. 개인 계정 설정과
활성화·비활성화 절차는 [`LangSmith 추적 운영 정책`](langsmith-tracing.md)을 따른다.

## Agent 객체 수명주기

FastAPI lifespan은 서버 프로세스를 시작할 때 다음 객체를 한 번 조립한다.

1. 런타임이 소유하는 HTTP client와 HCX-005 `ChatClovaX`, CLOVA `bge-m3` Query Embedder
2. `AsyncQdrantClient`와 `AsyncQdrantChunkRetriever`
3. 규칙 기반 `SearchRouter`, `SearchService`, `EvidenceFilter`
4. `policy`, `tax_payout`, `product` Domain Agent와 Main Supervisor
5. `AnswerService`

Kiwi 형태소 분석기는 요청을 받기 전에 전용 worker에서 한 번 준비한다. 실제 검색 중
형태소 분석도 event loop가 아니라 프로세스 수명의 `max_workers=1` executor에서만
실행한다. 요청 취소는 즉시 전파되며 이미 시작한 Python thread는 끝까지 실행되지만,
물리적 worker가 하나뿐이므로 다음 형태소 분석과 겹치지 않는다. HCX, query embedding과
Qdrant 네트워크 대기는 native async API를 사용한다. 오프라인 문서 적재의 batch
embedding `ThreadPoolExecutor`는 제품 `/answer` 경로와 별도다.

조립된 `AnswerService`는 같은 프로세스의 모든 `/answer` 요청에서 재사용한다. 요청별
메시지와 `SupervisorState`는 매번 새로 생성하므로 요청 간 상태를 공유하지 않는다.
Uvicorn worker를 여러 개 실행하면 worker 프로세스마다 Agent 객체가 하나씩 생성된다.
lifespan이 종료하면 새 요청을 막고 실행 중인 요청을 취소·회수한 뒤 Qdrant, embedding
HTTP client, HCX HTTP client 순으로 정리한다.

startup 도중 취소되거나 조립에 실패해도 이미 만든 client는 별도 cleanup task가
의존성 역순으로 닫는다. startup task에 취소가 반복되어도 cleanup task를 직접
취소하지 않고 완료까지 소유하므로 일부 client만 남지 않는다.

`AnswerService`는 취소된 요청을 기본 10초까지 기다린다. 그 안에 끝나지 않은
비협조적 task가 있으면 실행 중 client를 먼저 닫지 않고 명시적 close를 건너뛴다.
정상 Uvicorn 종료는 lifespan 전에 요청 task를 먼저 drain하므로 이 분기는 비정상적인
취소 지연에 대한 안전장치다. shutdown 호출을 무기한 막지 않으며, 남은 process 자원은
프로세스 종료 시 OS가 회수한다.

## 비동기 실행 예산

온라인 실행 상한은 [`AgentRuntimeConfig`](../../pension_agent/config/agent_runtime.py)와
Domain/Search 설정에 버전 관리한다. 기본값은 다음과 같으며 모두 **프로세스당** 값이다.

| 경계 | 기본 상한 | 포화 시 동작 |
|---|---:|---|
| 전체 `/answer` | 4 | 요청 전체 deadline 안에서 대기 |
| `/answer` 대기열 | 64 | 활성 4개와 대기 64개를 넘으면 즉시 정제된 503 반환 |
| HCX 모델 호출 | 4 | 모든 Supervisor·Domain graph가 공유해서 대기 |
| query embedding | 4 | provider 호출 전에 대기 |
| Qdrant 조회 | 4 | provider 호출 전에 대기, client connection pool도 4 |
| Domain Agent | 도메인별 3 | Domain 75초와 상위 deadline 중 빠른 시각까지 대기 |
| Search Service | 전체 공유 4 | 검색 45초와 상위 deadline 중 빠른 시각까지 대기 |

`/answer`의 기본 전체 제한은 180초다. capacity 대기, HCX retry, Domain, Search Service와 최종
응답 조립을 모두 요청 시작 시 만든 하나의 absolute deadline 안에 포함한다. timeout이나
ASGI `http.disconnect`는 하위 coroutine으로 전파되며 실행 슬롯을 돌려준다. 이미 원격
provider가 받은 작업의 중단까지 보장하지는 않는다. 활성 Agent 작업은 4개, capacity를
기다리는 요청은 64개로 제한하며 각 대기 요청도 180초 뒤 종료된다. 총 68개 admission이
모두 사용 중이면 새 요청은 내부 작업을 시작하지 않고 정제된 HTTP 503을 반환한다.
무제한 내부 worker queue나 무제한 대기열은 만들지 않는다.

이 상한은 분산 semaphore가 아니다. Uvicorn worker를 `N`개 실행하면 전체 배포의 실제
상한은 표의 값에 `N`을 곱한 수가 된다. worker 수를 늘릴 때는 HCX·embedding·Qdrant
quota를 함께 확인해야 한다. 현재 `make serve`는 `--workers`를 지정하지 않아 1개
프로세스를 사용한다.

`/health` 요청은 Agent나 검색 시스템을 실행하지 않으며 async event loop에서 바로
응답한다. 따라서 여러 `/answer`가 provider 응답을 기다리는 동안에도 같은 프로세스의
liveness를 확인할 수 있다. 다만 Agent 조립이 서버 시작 과정에 있으므로 연결 설정이
잘못되면 서버가 시작되지 않아 `/health`에도 접속할 수 없다.

## 배포 환경 실행

컨테이너나 외부 트래픽을 받는 배포 환경에서는 모든 네트워크 인터페이스에 바인딩하기
위해 `0.0.0.0`을 사용한다.

```bash
uv run uvicorn pension_agent.api.app:app \
  --host 0.0.0.0 \
  --port 8000
```

`0.0.0.0`은 서버의 바인딩 주소이며 브라우저에서 접속할 주소가 아니다. 배포
파이프라인은 이미지나 릴리스를 만든 정확한 Git 커밋 SHA를 `DEPLOY_COMMIT_SHA`로
자동 주입해야 한다. 사람이 배포 때마다 직접 입력하는 값으로 운영하지 않는다.

## 자주 발생하는 문제

| 증상 | 확인할 내용 |
|---|---|
| 서버 시작 실패 | `.env`의 CLOVA·Qdrant 연결 설정 확인 |
| `/answer`의 검색 실패 | Qdrant collection 이름, 적재 여부와 payload 계약 확인 |
| LangSmith에 trace가 생성되지 않음 | `.env`의 `LANGSMITH_*` 설정을 확인하고 서버를 `--env-file .env` 옵션으로 완전히 재시작 |
| `/answer` 한 번에 LangSmith root trace가 여러 개 생성됨 | async Task별 tracing context가 섞이지 않는지 확인하고 [`LangSmith 추적 운영 정책`](langsmith-tracing.md)의 정상 trace tree와 비교 |
| `Address already in use` | 8000번 포트를 쓰는 프로세스를 종료하거나 `--port 8001` 사용 |
| `/health`의 SHA가 `unknown` | 로컬에서는 정상이다. 배포 환경이면 SHA 주입 설정 확인 |
| 다른 기기에서 로컬 서버에 접속할 수 없음 | `127.0.0.1`은 로컬 전용이다. 외부 공개가 필요할 때만 보안 설정 후 바인딩 범위를 변경 |
| 코드 변경이 반영되지 않음 | 개발 중이면 `--reload`를 사용하거나 서버 재시작 |
