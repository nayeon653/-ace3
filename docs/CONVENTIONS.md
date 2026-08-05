# 개발 컨벤션

3인 팀이 충돌 없이 병렬로 작업하기 위한 규칙 전문이다. 역할과 담당 영역은
고정하지 않고 작업별로 정한다. 요약은 [`PROJECT_RULES.md`](../PROJECT_RULES.md) 참고.

## 브랜치

```
<type>/<short-description>

feat/ocr-pipeline
fix/embedding-timeout
docs/api-spec
exp/reranker-comparison
```

- `type`: 커밋 type과 같은 목록을 사용한다.
- `short-description`: 작업 결과를 설명하는 영문 소문자 kebab-case 명사구를 쓴다.
- 실제 GitHub 이슈가 있는 작업만 번호를 선택적으로 붙인다
  (예: `feat/12-ocr-pipeline`).
- 작업자는 Notion 담당자, 커밋 author, PR 작성자로 확인하며 브랜치명에는 넣지 않는다.
- 이미 만들어진 브랜치는 강제로 바꾸지 않고, 새 브랜치부터 이 규칙을 적용한다.
- 브랜치 수명은 최대 3일, 자동 생성 잠금 파일을 제외한 변경량은 400줄 내외를
  넘기지 않는다.
- 매일 아침 main에 rebase한다.
- main 통합은 squash merge. 머지 후 브랜치는 삭제한다 (단 `exp/`는 예외 —
  실험은 머지되지 않을 수 있으므로 남겨둔다).

```bash
# 생성
git switch main
git pull --ff-only
git switch -c feat/ocr-pipeline

# main 동기화
git fetch origin
git rebase origin/main

# squash merge 뒤 로컬 브랜치 정리
git switch main
git pull --ff-only
git branch -d feat/ocr-pipeline
```

## 커밋

```
<type>[optional scope][!]: <description>

예: feat(ingest): OCR 파이프라인 추가
    fix(agent): 임베딩 타임아웃 수정
    docs: API 명세 초안 작성
    refactor!: 응답 스키마 변경
```

- 허용 type은 `feat | fix | docs | refactor | test | chore | exp | perf | build |
  ci | revert`이다.
- scope는 변경 영역을 구분할 때만 선택적으로 사용한다.
- 호환되지 않는 변경은 type 또는 scope 뒤에 `!`를 붙인다.
- 설명은 한국어로 작성해도 되며, 의미가 드러나는 현재형 문구를 쓴다.
- 이슈 번호는 강제하지 않는다. 실제 이슈가 있을 때 본문이나 footer에 남긴다.
- 커밋 작성자는 각자 본인 명의로 남긴다. `git config user.email`을 GitHub에
  등록된 메일과 반드시 일치시킨다. 불일치 시 커밋이 계정에 연결되지 않아
  기여자가 사라진 것처럼 보인다.
- **Claude Code 등 AI 코딩 어시스턴트는 GitHub contributor에 절대 나타나지
  않는다.** 커밋을 대신 만들어주더라도 author/committer는 항상 요청한
  사람 본인의 git identity를 쓴다.
- **`Co-Authored-By` 트레일러는 금지한다.** 대회 규정상 제출 시스템은
  HyperCLOVA X만 사용해야 하며, 커밋 히스토리에 다른 LLM 명의가 남는 것은
  불필요한 오해를 만든다. 또한 이 트레일러는 GitHub이 해당 계정을
  contributor로 표시하게 만드는 원인이기도 하다. `.githooks/commit-msg`가
  이를 자동 차단한다.
- 의미 단위로 커밋한다. "wip", "update" 같은 메시지는 쓰지 않는다.

## PR

- 변경 내용과 이유, 검증 방법을 PR 템플릿에 작성한다.
- 승인 1인 필수.
- 실제 GitHub 이슈를 종료하는 PR만 본문에 `Closes #번호`를 적는다.
- 시크릿과 재생성 가능한 산출물을 포함하지 않는다.

## 리뷰

- 리뷰어는 최소 1명이며 작업 내용에 따라 정한다.
- 세제 계산 로직(`pension_agent/rules/`)과 프롬프트(`pension_agent/prompts/`)
  변경은 수치/문구 diff를 꼼꼼히 본다 — 이 저장소에서 가장 비싼 실수가 나는
  지점이다.

## 태그

- `v0.0-scaffold`: 초기 스캐폴딩 완료 시점.
- `v1.0-freeze`: Phase 2(동결) 진입 시점.
- `v1.0-final`: 제출 시점.

## 3단계 동결 정책

| Phase | 기간 | 허용 범위 | PR 승인 | 비고 |
|---|---|---|---|---|
| Phase 1 개발 | ~ 2026-08-23 | 자유로운 기능 개발 | 1인 | |
| Phase 2 동결 | 2026-08-24 ~ 2026-09-06 | 버그픽스, 프롬프트 미세조정만 | 2인 | 진입 시 `v1.0-freeze` 태그 |
| Phase 3 봉인 | 2026-09-06 이후 | 모든 push 차단 | - | `v1.0-final` 태그, remote 제거 |

Phase 2에서는 새 기능이나 큰 리팩터링을 시작하지 않는다. Phase 3 진입 후에는
`.githooks/pre-push`가 모든 push를 차단하며, 평가기간 중 서버가 죽어도
코드로 대응하지 않는다(정량평가 0점 리스크와 실격 리스크 중 실격이 항상
더 크다).
