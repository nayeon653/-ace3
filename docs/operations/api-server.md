# API 서버 실행과 확인

FastAPI 서버를 로컬에서 실행하고 동작을 확인하는 방법과 배포 환경의 차이를 정리한다.
외부 요청·응답 필드 계약은 [`docs/api-spec.md`](../api-spec.md)를 따른다.

## 최초 준비

저장소 루트에서 개발 의존성을 설치하고 로컬 환경 파일을 만든다.

```bash
uv sync --dev
cp .env.example .env
```

`.env`에서 `CLOVASTUDIO_API_KEY`에 발급받은 실제 키를 입력한다. 키를 문서, 로그,
커밋이나 채팅에 남기지 않는다.

```dotenv
CLOVASTUDIO_API_KEY=<발급받은 실제 API 키>
CLOVASTUDIO_API_BASE_URL=https://clovastudio.stream.ntruss.com/v1/openai
```

`.env.example`을 복사했다면 `CLOVASTUDIO_API_BASE_URL`에는 기본 주소가 이미 있으므로
일반적인 로컬 실행에서는 수정하지 않는다. 서버는 시작할 때 Agent 객체를 조립하므로
필수 연결 설정이 없으면 시작하지 않는다.

## 가장 간단한 로컬 실행

일반적인 로컬 테스트는 다음 한 줄이면 충분하다.

```bash
uv run uvicorn pension_agent.api.app:app
```

Uvicorn 기본값에 따라 `127.0.0.1:8000`에서 실행된다. 로컬에서는 배포 버전 추적이
필수가 아니므로 `DEPLOY_COMMIT_SHA`를 생략할 수 있다. 생략하면 `/health`의
`commit_sha`는 `unknown`이다.

코드 변경 시 서버를 자동 재시작하려면 다음과 같이 실행한다.

```bash
uv run uvicorn pension_agent.api.app:app --reload
```

자동 재시작 때마다 서버 프로세스와 Agent 객체가 새로 생성된다.

## 옵션을 명시하는 로컬 실행

바인딩 주소, 포트와 현재 커밋을 명시해서 확인하려면 다음 명령을 사용한다.

```bash
DEPLOY_COMMIT_SHA="$(git rev-parse HEAD)" \
uv run uvicorn pension_agent.api.app:app \
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

1. `ChatClovaX` 모델
2. 도메인 Agent Tool과 Main Supervisor
3. `AnswerService`

조립된 `AnswerService`는 같은 프로세스의 모든 `/answer` 요청에서 재사용한다. 요청별
메시지와 `SupervisorState`는 매번 새로 생성하므로 요청 간 상태를 공유하지 않는다.
Uvicorn worker를 여러 개 실행하면 worker 프로세스마다 Agent 객체가 하나씩 생성된다.

`/health` 요청은 Agent나 검색 시스템을 실행하지 않는다. 다만 Agent 조립이 서버 시작
과정에 있으므로 연결 설정이 잘못되면 서버가 시작되지 않아 `/health`에도 접속할 수
없다.

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
| 서버 시작 실패 | `.env`의 `CLOVASTUDIO_API_KEY`와 `CLOVASTUDIO_API_BASE_URL` 확인 |
| `Address already in use` | 8000번 포트를 쓰는 프로세스를 종료하거나 `--port 8001` 사용 |
| `/health`의 SHA가 `unknown` | 로컬에서는 정상이다. 배포 환경이면 SHA 주입 설정 확인 |
| 다른 기기에서 로컬 서버에 접속할 수 없음 | `127.0.0.1`은 로컬 전용이다. 외부 공개가 필요할 때만 보안 설정 후 바인딩 범위를 변경 |
| 코드 변경이 반영되지 않음 | 개발 중이면 `--reload`를 사용하거나 서버 재시작 |
