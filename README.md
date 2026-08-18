# -ace3

private 레포입니다.

제10회 2026 미래에셋증권 AI Festival — 배정 주제 "연금 Agent".
연금 상품·제도·세제 문서를 근거로 자연어 질의에 답하는 AI Agent와,
주최측이 GET으로 호출할 평가용 API 서버를 만든다.

## 스캐폴딩 직후 실행 명령 (관리자 1회)

```bash
chmod +x .githooks/*
git config core.hooksPath .githooks
```

## 팀원 3인 — clone 직후 각자 1회 실행 (필수)

```bash
git clone <repo-url>
cd -ace3

# 1. 훅 경로 설정 (또는 make hooks)
git config core.hooksPath .githooks
chmod +x .githooks/*

# 2. 커밋 작성자 정보 — GitHub 등록 메일과 반드시 일치시킬 것
git config user.name "<이름 또는 GitHub id>"
git config user.email "<GitHub에 등록된 메일>"

# 3. 개발 환경 (Python 3.12, uv 필요: https://docs.astral.sh/uv/)
uv sync --dev
cp .env.example .env        # 값 채워넣기 (절대 커밋 금지)
```

## 아키텍처 요약

```
[오프라인 문서 준비]
문서(PDF/DOCX/XLSX/PPTX)
  → tools/docling_parser(파싱/OCR)
  → data/processed/docling
  → ingest(정규화)
  → retrieval(인덱싱)

[서비스 요청]
GET /answer → api(FastAPI) → agent(라우터/도구 오케스트레이션)
                                ├→ retrieval(검색)
                                ├→ rules(결정론적 세제 계산)
                                └→ prompts + HyperCLOVA X
                                   (Tool 선택·최종 답변: HCX-005)
```

원칙: **계산은 코드가, 설명은 LLM이 한다.** 세액공제 한도·세율 등 확정
수치는 `pension_agent/rules/`의 결정론적 함수에서만 나오며, LLM은 의도 분류·
근거 요약·조건 분기 설명만 담당한다. 자세한 원칙은 [`PROJECT_RULES.md`](PROJECT_RULES.md)
참고.

모듈 의존성은 HTTP 인터페이스에서 도메인 모듈 방향으로만 흐릅니다.

```text
api → agent → retrieval
          ├→ rules
          └→ prompts

ingest → retrieval
```

`core`는 공용 타입·프로토콜·예외만 제공하고, `config`는 설정 로딩과 기본값을
담습니다. 운영 경로인 `api`와 `agent`는 오프라인 파싱 모듈인 `ingest`를 import하지
않습니다. Docling 파서는 API 환경과 의존성을 섞지 않도록 자체 잠금 환경을 가진
저장소 내부 오프라인 도구로 실행합니다.

## 빠른 시작

```bash
make setup   # 런타임 + 개발 의존성 설치
make check   # Ruff 린트·포맷 + mypy 타입 검사 + pytest
make build   # wheel + source distribution 빌드

make qdrant-up     # 로컬 Qdrant 실행
make qdrant-check  # readiness + Python 클라이언트 연결 확인
make qdrant-down   # 로컬 Qdrant 종료 (데이터 유지)

make setup-parser  # Docling 파서 전용 환경 설치
make parser-test   # 파서 단위 테스트
```

로컬 Qdrant의 대시보드, 연결 주소, 데이터 유지와 초기화 방법은
[`docs/operations/qdrant-local.md`](docs/operations/qdrant-local.md)를 따른다.

`.env`에 CLOVA Studio 연결 정보를 설정한 뒤 FastAPI 서버를 로컬에서 실행합니다.
Uvicorn 기본값인 `127.0.0.1:8000`을 사용하므로 별도 host와 port 옵션은 필요하지
않습니다.

```bash
uv run uvicorn pension_agent.api.app:app --env-file .env
```

`--env-file .env`는 로컬 설정을 Uvicorn 서버 프로세스의 환경변수로 주입한다.
`ClovaStudioConnection`은 Pydantic Settings로 `.env`를 직접 읽지만, LangSmith 기본
tracing은 프로세스 환경의 `LANGSMITH_*`를 읽으므로 이 옵션이 필요하다.

로컬에서는 `DEPLOY_COMMIT_SHA`를 생략해도 되며 `/health`에 `unknown`으로 표시됩니다.

LangSmith tracing은 기본적으로 꺼져 있습니다. 개발자가 개인 무료 계정의 환경변수를
로컬에 등록해 활성화하면 일반 `/answer` 요청을 포함한 모든 Agent 실행을 추적합니다.
개인 계정·project 설정과 활성화 방법은
[`docs/operations/langsmith-tracing.md`](docs/operations/langsmith-tracing.md)를 따릅니다.
서버 시작 과정에서 HCX 모델, Main Supervisor와 `AnswerService`를 프로세스당 한 번
조립하고 모든 `/answer` 요청에서 재사용합니다.

운영 확인용 `GET /health`는 LLM이나 검색 시스템을 호출하지 않습니다. 평가용
`GET /answer`의 정확한 요청·응답과 오류 계약은
[`docs/api-spec.md`](docs/api-spec.md)를 참고하세요. 로컬 확인, 배포 실행, 환경변수와
문제 해결 방법은 [`API 서버 실행과 확인`](docs/operations/api-server.md)에 있습니다.

PR과 `main` 브랜치 push에는 Python 3.12 기반 Backend CI가 실행되며,
`make check`와 패키지 빌드·설치 가능 여부를 검증합니다.

Docling 오프라인 파싱 스크립트와 FastAPI 평가 실행 진입점이 제공됩니다. 제품 검색과
평가 하네스는 각 기능을 구현하는 PR에서 함께 추가합니다.

### HyperCLOVA X 설정

Main Supervisor는 Tool 선택과 최종 답변 생성에 같은 HCX-005 인스턴스를 사용합니다.
모델명, 생성 토큰 수, temperature, timeout과 retry는 환경변수가 아니라
[`pension_agent/config/hcx.py`](pension_agent/config/hcx.py)의 불변 config에서 버전
관리합니다. 현재 모델명과 생성 파라미터는 실연결 검증 전에 임의로 정한 초기값이며,
후속 검증 결과에 따라 HyperCLOVA X 범위 안에서 config와 결정 기록을 변경할 수
있습니다.

Pydantic Settings가 로컬 `.env` 또는 프로세스 환경에서 인증·연결 정보만 읽습니다.

```dotenv
CLOVASTUDIO_API_KEY=<발급받은 API 키>
CLOVASTUDIO_API_BASE_URL=https://clovastudio.stream.ntruss.com/v1/openai
```

애플리케이션 조립 경계에서는 환경 설정을 읽은 뒤 Factory가 만든 모델을 Main
Supervisor에 주입합니다.

```python
from pension_agent.agent.model_factory import create_chat_clovax
from pension_agent.agent.orchestration import create_main_supervisor
from pension_agent.config import MAIN_SUPERVISOR_HCX_CONFIG, ClovaStudioConnection

connection = ClovaStudioConnection()
model = create_chat_clovax(
    config=MAIN_SUPERVISOR_HCX_CONFIG,
    connection=connection,
)
supervisor = create_main_supervisor(model=model, tools=domain_tools)
```

## 디렉토리 구조

| 디렉토리 | 내용 |
|---|---|
| `pension_agent/ingest/` | 파싱 artifact 검증·정규화·retrieval 연계 |
| `pension_agent/retrieval/` | 청킹·임베딩·검색 |
| `pension_agent/agent/` | 에이전트별 모듈, 공용 계약, 오케스트레이션 |
| `pension_agent/prompts/` | 실행 주체별 프롬프트 리소스 |
| `pension_agent/rules/` | 세제 계산기 (결정론적) |
| `pension_agent/api/` | FastAPI 라우트·스키마·HTTP 예외 변환 |
| `pension_agent/core/` | 공용 타입·프로토콜·예외 |
| `pension_agent/config/` | 설정 로더와 안전한 런타임 기본값 |
| `tools/docling_parser/` | 고정 로컬/NAVER OCR 프로필을 제공하는 오프라인 파싱 도구 |
| `infra/` | Docker·배포·모니터링 |
| `data/` | 원본·중간 산출물·검색 인덱스 (Git 제외) |
| `evals/questions/` | 평가 질의셋 |

`pension_agent/agent/`는 실행 책임별 모듈로 나눈다.

| 경로 | 책임 |
|---|---|
| `contracts/` | Main·Domain·API가 공유하는 입출력 계약 |
| `orchestration/` | Main Supervisor, 상태, Domain Tool Adapter, 실행 서비스 |
| `search/` | Search Agent, 검색 Port, Tool, 미들웨어, 검색 스키마 |
| `policy/` | 업무·제도 Domain Agent |
| `tax_payout/` | 세제·수령 Domain Agent |
| `product/` | 상품·운용 Domain Agent |

구체 Domain Agent의 선택과 Tool 등록은 `pension_agent/api/bootstrap.py`에서 수행한다.
`orchestration`은 구체 Domain Agent를 import하지 않으며, Domain Agent끼리도 직접
의존하지 않는다. Search Agent는 저장소 구현 대신 `ChunkRetriever` Port에 의존하고,
`retrieval/QdrantChunkRetriever`가 Qdrant 접근을 구현한다.
| `evals/harness/` | 평가 실행기 |
| `docs/` | 컨벤션, 결정 기록, 실험 로그, API 명세, 제안서 |
| `tests/` | 테스트 |

## 더 읽기

- [`PROJECT_RULES.md`](PROJECT_RULES.md) — 절대 원칙, 컨벤션 요약, 모듈 의존성 방향
- [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) — 도구별 공통 정책 진입점
- [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) — 브랜치·커밋·PR·리뷰·태그 규칙 전문
- [`docs/decisions/`](docs/decisions/README.md) — 아키텍처·프로세스 결정 기록
- [`docs/api-spec.md`](docs/api-spec.md) — 평가용 API 명세
- [`docs/qdrant-retrieval-spec.md`](docs/qdrant-retrieval-spec.md) — Qdrant 저장·검색 계약 진입점
- [`docs/operations/api-server.md`](docs/operations/api-server.md) — API 서버 로컬 실행·배포·문제 해결
- [`docs/operations/qdrant-local.md`](docs/operations/qdrant-local.md) — 로컬 Qdrant 실행·연결·데이터 관리
- [`docs/operations/document-parsing.md`](docs/operations/document-parsing.md) — Docling 실행·저장·검수 정책
- [`SUBMISSION.md`](SUBMISSION.md) — 제출물 체크리스트 및 마감
