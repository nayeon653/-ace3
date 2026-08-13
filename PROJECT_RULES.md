# 프로젝트 공통 규칙

이 저장소에서 코드를 작성하는 모든 사람(과 코딩 에이전트)이 지켜야 할 규칙이다.
대회: 제10회 2026 미래에셋증권 AI Festival — 배정 주제 "연금 Agent".

## 절대 어기지 말 것

1. **LLM은 HyperCLOVA X만 사용 가능.** Main Supervisor의 Tool 선택과 최종 답변
   생성에는 HCX-005 단일 모델을 사용한다. 제품(평가 대상 시스템) 안에서 다른
   LLM을 호출하는 코드를 작성하지 않는다. 위반 시 대회 규정상 평가대상 제외
   사유다. HCX-005는 실연결 검증 전에 임의로 정한 초기 모델이며, 추후 검증 결과에
   따라 HyperCLOVA X 범위 안에서 버전 관리되는 config와 결정 기록을 변경할 수 있다.
   (개발 보조 도구로서의 코딩 어시스턴트 사용 가부는 별도 확인 대상이며,
   이 규칙은 제출 시스템 자체에 적용된다.)
2. **제출 마감은 2026-09-06 23:59.** 마감 이후 커밋·push·배포 등 변경 행위가
   발견되면 실격이다. `.githooks/pre-push`가 이를 강제하지만, 훅에만 의존하지
   않는다.
3. **평가기간(2026-09-07 ~ 09-20) 중 API 서버가 죽으면 정량평가 0점.** 배포
   안정성에 관련된 변경은 특히 신중히 다룬다.
4. **`GET /answer` 응답 JSON은 정확히 5개 필드만 포함한다:**
   `question_id`, `question`, `retrieved_context`, `think_trace`, `answer`.
5. **제공된 문서 데이터가 최종 근거다.** 외부 지식은 보조 수단일 뿐이며,
   제공 자료와 상충하면 제공 자료를 따른다.

## 핵심 개발 원칙

1. **계산은 코드가, 설명은 LLM이 한다.** 세액공제 한도, 연금소득세율,
   연금수령한도 등 확정 수치는 `pension_agent/rules/`의 결정론적 파이썬
   함수에서만 나온다.
   LLM은 의도 분류, 도구 선택, 근거 요약, 조건 분기 설명만 담당하며 수치를
   직접 생성하지 않는다.
2. **역질문은 되묻기가 아니라 조건 분기 응답이다.** API가 stateless GET이라
   되물을 수 없다. 한 응답 안에 "확인이 필요한 조건"과 "조건별 결론"을 함께
   제시한다. 단정적 추천은 금지한다.
3. **`retrieved_context`는 precision도 평가된다.** top-k를 통째로 넣지 말고
   리랭킹 후 컷오프하며, 답변에 실제로 인용한 근거만 남긴다. 무관하거나
   대상이 다른 근거를 포함하면 감점된다.
4. **모든 답변에 근거 문서를 표시한다.** Context에 없는 내용을 생성하지 않는다
   (환각 금지).
5. **매일 저녁 '동작하는 버전'을 유지한다.** 의미 단위로 커밋한다.

## 컨벤션 요약

전문은 [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) 참고.

- 브랜치: `<type>/<short-description>` (예: `feat/ocr-pipeline`,
  `fix/embedding-timeout`). 실제 GitHub 이슈가 있을 때만 번호를 선택적으로 붙인다.
- 커밋: 가벼운 Conventional Commits 형식인 `type(scope): 설명`을 사용한다
  (예: `feat(ingest): OCR 파이프라인 추가`). scope는 선택이며 이슈 번호는
  강제하지 않는다.
- 커밋 작성자는 각자 본인 명의. `git config user.email`을 GitHub 등록 메일과
  일치시킬 것.
- **AI 코딩 어시스턴트(Claude Code 등)는 GitHub contributor 목록에 절대 나타나면
  안 된다.** 커밋의 author/committer는 항상 그 커밋을 요청한 사람 본인의 git
  identity(`user.name`/`user.email`)를 사용한다. Claude를 author나 committer로
  설정하지 않는다.
- **`Co-Authored-By` 트레일러 금지.** Claude Code 등 AI 도구가 커밋 메시지에
  `Co-Authored-By: Claude <...>` 같은 트레일러를 자동으로 붙이지 않도록 한다.
  대회의 LLM 사용 제약(HyperCLOVA X만 허용)과 관련한 오해를 막기 위함이며,
  동시에 위 contributor 비노출 원칙을 지키기 위한 장치이기도 하다.
- main 직접 push 금지, 긴급 수정도 `fix/` 브랜치 → PR.
- main 통합은 squash merge. PR 승인 1인 필수.

## 디렉토리 역할

팀 역할과 담당 디렉토리는 아직 고정하지 않는다. 담당자는 작업별로 정하고,
디렉토리는 아래 기능 경계만 나타낸다.

| 디렉토리 | 내용 |
|---|---|
| `pension_agent/ingest/` | 파싱 artifact 검증·정규화·retrieval 연계 |
| `pension_agent/retrieval/` | 청킹·임베딩·검색 |
| `pension_agent/agent/` | 라우터·도구·오케스트레이션 |
| `pension_agent/prompts/` | 프롬프트 파일 (코드 내 인라인 문자열 금지) |
| `pension_agent/rules/` | 세제 계산기 (결정론적) |
| `pension_agent/api/` | FastAPI 라우트·스키마·HTTP 예외 변환 |
| `infra/` | Docker·배포·모니터링 |
| `evals/` | 품질 평가 데이터와 실행기 |
| `pension_agent/config/` | 설정 로더와 안전한 기본값 |
| `tools/docling_parser/` | 제품 런타임과 격리된 오프라인 Docling 파싱 도구 |
| `docs/` | 명세·컨벤션·결정·실험 기록 |

`docs/` 전체가 append-only인 것은 아니다. API 명세와 컨벤션은 현재 상태에 맞게
수정하고, 채택된 결정 기록과 완료된 실험 기록은 정해진 정책에 따라 보존한다.

## 모듈 의존성 방향

의존성은 아래 방향으로만 흐른다. 표에 없는 기능 모듈 import는 허용하지 않는다.

| 모듈 | import 가능한 내부 모듈 |
|---|---|
| `core` | 없음 |
| `config` | `core` |
| `rules` | `core`, `config` |
| `retrieval` | `core`, `config` |
| `ingest` | `core`, `config`, `retrieval` |
| `agent` | `core`, `config`, `retrieval`, `rules`, `prompts` |
| `api` | `core`, `config`, `agent` |

- `core`에는 공용 타입·프로토콜·예외만 두고 기능 모듈을 import하지 않는다.
- `config`는 설정 로더와 기본값을 소유하며 기능 로직을 포함하지 않는다.
- `prompts`는 실행 시 읽는 리소스 패키지이며 다른 기능 모듈을 import하지 않는다.
- `api`는 `retrieval`이나 `rules`를 직접 호출하지 않고 `agent`를 통해 사용한다.
- 운영 경로인 `api`, `agent`, `retrieval`, `rules`는 `ingest`와 파싱 라이브러리를
  import하지 않는다.
- 현재 Docling 파서는 `tools/docling_parser/`의 독립 잠금 환경에서 오프라인으로
  실행하며 제품 런타임에서 import하지 않는다. 애플리케이션 내부 파서를 새로
  추가할 때는 `ingest` 구현과 함께 별도 의존성 그룹으로 관리한다.

## 문서 파싱 운영

- 문서 파싱의 실행·저장·검수 정책은
  [`docs/operations/document-parsing.md`](docs/operations/document-parsing.md)를 유일한
  원본으로 사용한다.
- Codex와 Claude Code의 로컬/NAVER Skill에는 선택 조건과 중앙 문서 경로만 둔다.
  실행 명령이나 운영 규칙을 Skill 본문에 복제하지 않는다.
- 원본은 `data/raw/`, 파싱 bundle은 `data/processed/docling/`에 두고 둘 다 Git에
  커밋하지 않는다.
- 현재 작업 범위는 파싱까지다. 청킹·임베딩 정책을 파서 코드나 Skill에 미리 넣지
  않는다.

## 개발 메모

```bash
# 최초 1회 세팅
git config core.hooksPath .githooks
uv sync --dev
cp .env.example .env   # 값 채워넣기 (커밋 금지)

# 자주 쓰는 명령 (Makefile 참고)
make setup   # 런타임 + 개발 의존성 설치
make check   # ruff + pytest
make build   # wheel + source distribution 빌드
make setup-parser  # 독립 Docling 파서 환경 설치
make parser-test   # Docling 파서 단위 테스트
```

애플리케이션 실행 명령은 해당 진입점이 구현되는 PR에서 함께 추가한다.

## 하지 말 것

- `.env`, API 키, 시크릿을 커밋하지 않는다 (`.githooks/pre-commit`이 1차
  방어선이며, 사람이 2차 방어선이다).
- 코드로 드러나지 않는 제약이 아니면 주석을 달지 않는다.
- 필요한 설명 주석과 docstring은 한국어로 작성한다. 린터 지시자, 코드 식별자와
  외부 API의 고유 명칭은 원문을 유지한다.
- 하드코딩된 세액공제 한도·세율 등을 LLM 프롬프트나 애플리케이션 코드에
  직접 박아넣지 않는다 — 반드시 `pension_agent/rules/`를 거친다.
- 마감(2026-09-06 23:59) 이후 어떤 형태로든 변경 행위를 하지 않는다.
