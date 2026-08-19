---
status: accepted
date: 2026-08-19
type: architecture
related:
  - 20260813-main-supervisor-domain-agent-tools.md
  - 20260813-hcx-005-model-factory.md
supersedes: []
superseded-by: []
---

# 온라인 Agent 실행 경로를 native async로 전환

## 배경

기존 `/answer` 경로는 FastAPI의 동기 endpoint와 Domain/Search별
`ThreadPoolExecutor`를 중첩해서 사용했다. HCX, query embedding과 Qdrant 호출은 대부분
CPU 계산이 아니라 네트워크 응답을 기다리는 작업인데도 요청마다 여러 worker thread를
점유했다.

동기 future의 바깥 timeout은 이미 실행 중인 thread를 중단하지 못했다. 따라서 응답은
timeout이어도 내부 Agent가 계속 실행됐고, answer 요청이 AnyIO worker pool을 채우면
`/health`까지 같은 pool을 기다릴 수 있었다. Main Supervisor 전체를 제한하는 요청
deadline과 provider별 전역 동시성 예산도 없었다.

## 결정

온라인 제품 경로를 다음과 같이 end-to-end native async로 실행한다.

- FastAPI `/answer` → `AnswerService` → Main Supervisor → Domain → Search를
  `async`/`await`와 LangGraph `ainvoke()`로 연결한다.
- HCX는 `ChatClovaX`의 async 호출, query embedding은 `aembed_query()`, 검색은
  `AsyncQdrantClient`를 사용한다.
- 모든 LangChain Tool을 coroutine으로 만들어 sync Tool의 executor fallback을 남기지
  않는다.
- 요청 시작 시 monotonic absolute deadline 하나를 만들고 `ExecutionContext`로 하위
  graph에 전달한다. Domain 75초와 Search 45초는 상위 deadline을 연장하지 않는다.
- 프로세스당 활성 answer, HCX, embedding, Qdrant 호출을 각각 4개로 제한한다. Domain은
  종류별 3개, Search는 전체 4개를 사용하며 capacity 대기도 각 deadline에 포함한다.
- 활성 answer 4개 외에 capacity를 기다리는 answer는 64개만 admission한다. 총 68개가
  사용 중이면 새 요청은 Agent 작업을 시작하지 않고 정제된 HTTP 503으로 거절한다.
- `/answer`는 ASGI `http.disconnect`를 감시하고 연결이 먼저 끊기면 실행 중 answer
  coroutine에 취소를 전파한다.
- HCX·embedding의 sync/async HTTP client와 Qdrant async client는 runtime이 소유한다.
  shutdown은 활성 요청을 취소·회수한 뒤 의존성의 역순으로 client를 닫는다.
  startup 부분 조립 cleanup은 별도 task가 소유해 반복 취소 중에도 끝까지 진행한다.
- Kiwi는 CPU 작업이므로 startup에서 prewarm하고, 실제 tokenization만 프로세스 수명의
  단일 worker executor에서 실행한다. host task는 즉시 취소할 수 있지만 물리적 worker가
  하나뿐이라 남은 CPU 작업과 다음 tokenization이 겹치지 않는다.
- 오프라인 문서 적재의 제한된 batch embedding `ThreadPoolExecutor`는 이 결정의 범위에
  포함하지 않는다.

## 대안

### 기존 bounded thread pool 유지

변경 범위는 작지만 timeout 뒤 실행 중 worker를 회수할 수 없고, 중첩 pool과 LangSmith
context 전달 경계를 계속 관리해야 한다. 온라인 경로의 주요 SDK가 native async를
지원하므로 채택하지 않았다.

### endpoint와 graph만 부분 async로 변경

동기 Tool과 Qdrant client가 event loop를 직접 막거나 LangChain executor로 fallback한다.
코드의 겉모양만 async가 되고 취소·thread 감소 효과를 얻지 못하므로 채택하지 않았다.

## 결과

- provider 대기 중 event loop는 다른 answer와 `/health`를 처리할 수 있다.
- timeout과 클라이언트 취소가 하위 coroutine으로 전파되고 실행 permit이 반환된다.
- async task가 `contextvars`를 복사하므로 동시 요청의 LangSmith parent가 자연스럽게
  분리되며 요청 하나는 `main_supervisor` root 하나로 관측된다.
- 단일 질문의 모델→Tool 의존 순서나 provider 자체 지연은 줄지 않는다. 이 결정의 주된
  효과는 동시 요청 자원 사용, liveness, 취소와 수명주기 안정성이다.
- 활성 Agent 작업은 semaphore로 제한하고 대기 admission도 64개로 hard-limit한다.
  admission된 대기 수명은 180초 전체 deadline으로 제한하며 초과 요청은 503을 받는다.
- 동시성 상한은 프로세스 단위다. Uvicorn worker가 `N`개면 배포 전체 provider 상한도
  `N`배가 되므로 worker 수와 provider quota를 함께 운영해야 한다.
- coroutine 취소는 client의 대기를 중단하지만, 이미 원격 provider가 받은 작업 자체의
  중단까지 보장하지는 않는다.
- shutdown 취소에 10초 안에 응답하지 않는 task가 있으면 client를 먼저 닫지 않는다.
  정상 Uvicorn 종료는 lifespan 전에 요청을 drain한다. 비정상적인 취소 지연에서는
  명시적 client close를 건너뛰고 shutdown 호출을 반환하며, OS의 process 자원 회수에
  맡긴다.

## 관련 자료

- [GitHub issue #58](https://github.com/nayeon653/-ace3/issues/58)
- [API 서버 실행과 비동기 예산](../operations/api-server.md)
- [LangSmith 추적 운영](../operations/langsmith-tracing.md)
