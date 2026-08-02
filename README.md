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
문서(PDF/DOCX/XLSX/PPTX) → ingest(파싱/OCR/정규화) → retrieval(인덱싱/검색)
                                                                  │
GET /answer ─→ api(FastAPI) ────→ agent(라우터/도구 오케스트레이션) ──┤
                                        │                          │
                                        ├─→ rules(결정론적 세제 계산) │
                                        └─→ prompts + HyperCLOVA X ─┘
                                        (function calling: HCX-005,
                                         생성: HCX-DASH-002)
```

원칙: **계산은 코드가, 설명은 LLM이 한다.** 세액공제 한도·세율 등 확정
수치는 `pension_agent/rules/`의 결정론적 함수에서만 나오며, LLM은 의도 분류·
근거 요약·조건 분기 설명만 담당한다. 자세한 원칙은 [`CLAUDE.md`](CLAUDE.md)
참고.

## 빠른 시작

```bash
make setup   # 의존성 설치
make ingest  # 원본 문서 → 파싱/OCR
make index   # 청킹/임베딩/인덱싱
make serve   # 로컬 서버 기동 (GET /answer)
make eval    # 평가셋 실행
make check   # ruff + pytest
```

## 디렉토리 구조

| 디렉토리 | 소유자 | 내용 |
|---|---|---|
| `pension_agent/ingest/` | A | 파싱·OCR·정규화 |
| `pension_agent/retrieval/` | A | 청킹·임베딩·검색 |
| `pension_agent/agent/` | B | 라우터·도구·오케스트레이션 |
| `pension_agent/prompts/` | B | 프롬프트 파일 |
| `pension_agent/rules/` | C | 세제 계산기 (결정론적) |
| `pension_agent/api/` | C | FastAPI 라우트·스키마·HTTP 예외 변환 |
| `pension_agent/core/` | 공동 | 공용 설정 로더·모델·예외 |
| `pension_agent/config/defaults/` | A/B/C 분할 | 안전한 런타임 기본 설정 |
| `infra/` | C | Docker·배포·모니터링 |
| `data/` | 로컬 전용 | 원본·중간 산출물·검색 인덱스 (Git 제외) |
| `evals/questions/` | A/B/C 분할 | 평가 질의셋 (`set_a.jsonl` / `set_b.jsonl` / `set_c.jsonl`) |
| `evals/harness/` | C | 평가 실행기 |
| `docs/` | 공동 | 컨벤션, 결정 기록, 실험 로그, API 명세, 제안서 |
| `tests/` | 공동 | 테스트 |

## 더 읽기

- [`CLAUDE.md`](CLAUDE.md) — 절대 원칙, 컨벤션 요약, 디렉토리 소유권
- [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) — 브랜치·커밋·PR·리뷰·태그 규칙 전문
- [`docs/decisions/`](docs/decisions/README.md) — 아키텍처·프로세스 결정 기록
- [`docs/api-spec.md`](docs/api-spec.md) — 평가용 API 명세
- [`SUBMISSION.md`](SUBMISSION.md) — 제출물 체크리스트 및 마감
