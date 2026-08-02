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

# 3. 개발 환경 (uv 설치 필요: https://docs.astral.sh/uv/)
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
                                   (function calling: HCX-005,
                                    생성: HCX-DASH-002)
```

원칙: **계산은 코드가, 설명은 LLM이 한다.** 세액공제 한도·세율 등 확정
수치는 `pension_agent/rules/`의 결정론적 함수에서만 나오며, LLM은 의도 분류·
근거 요약·조건 분기 설명만 담당한다. 자세한 원칙은 [`CLAUDE.md`](CLAUDE.md)
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
make check   # ruff + pytest
make build   # wheel + source distribution 빌드

make setup-parser  # Docling 파서 전용 환경 설치
make parser-doctor # 로컬 OCR 환경과 고정 프로필 확인
make parser-test   # 파서 단위 테스트
```

Docling 오프라인 파싱 CLI는 제공됩니다. 제품 검색·API·평가 실행 진입점은 아직
구현하지 않았으며 각 기능을 구현하는 PR에서 함께 추가합니다.

## 디렉토리 구조

| 디렉토리 | 내용 |
|---|---|
| `pension_agent/ingest/` | 파싱 artifact 검증·정규화·retrieval 연계 |
| `pension_agent/retrieval/` | 청킹·임베딩·검색 |
| `pension_agent/agent/` | 라우터·도구·오케스트레이션 |
| `pension_agent/prompts/` | 프롬프트 파일 |
| `pension_agent/rules/` | 세제 계산기 (결정론적) |
| `pension_agent/api/` | FastAPI 라우트·스키마·HTTP 예외 변환 |
| `pension_agent/core/` | 공용 타입·프로토콜·예외 |
| `pension_agent/config/` | 설정 로더와 안전한 런타임 기본값 |
| `tools/docling_parser/` | 고정 로컬/NAVER OCR 프로필을 제공하는 오프라인 CLI |
| `infra/` | Docker·배포·모니터링 |
| `data/` | 원본·중간 산출물·검색 인덱스 (Git 제외) |
| `evals/questions/` | 평가 질의셋 |
| `evals/harness/` | 평가 실행기 |
| `docs/` | 컨벤션, 결정 기록, 실험 로그, API 명세, 제안서 |
| `tests/` | 테스트 |

## 더 읽기

- [`CLAUDE.md`](CLAUDE.md) — 절대 원칙, 컨벤션 요약, 모듈 의존성 방향
- [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) — 브랜치·커밋·PR·리뷰·태그 규칙 전문
- [`docs/decisions/`](docs/decisions/README.md) — 아키텍처·프로세스 결정 기록
- [`docs/api-spec.md`](docs/api-spec.md) — 평가용 API 명세
- [`docs/operations/document-parsing.md`](docs/operations/document-parsing.md) — Docling 실행·저장·검수 정책
- [`SUBMISSION.md`](SUBMISSION.md) — 제출물 체크리스트 및 마감
