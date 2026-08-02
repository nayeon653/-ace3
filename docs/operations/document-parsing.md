# 문서 파싱 운영 정책

이 문서는 `-ace3`의 Docling 파싱 실행, 데이터 저장, 외부 OCR, 실패 처리와 검수
정책의 **유일한 원본**이다. `.agents/skills/`와 `.claude/skills/`의 Skill은 이 문서를
찾아 읽게 하는 발견용 진입점이며, 명령과 정책을 복제하지 않는다.

## 범위와 원칙

- 현재 범위는 PDF, DOCX, PPTX, XLSX를 파싱해 구조화 artifact bundle을 만드는
  단계까지다. 청킹, 임베딩과 검색 인덱스 생성은 포함하지 않는다.
- 파서는 `tools/docling_parser/`의 독립 오프라인 프로젝트로 실행한다. 평가 API와
  `pension_agent` 런타임에서 파서 패키지를 import하지 않는다.
- 일반 요청에는 `docling-local-ocr-v1`을 사용한다. NAVER OCR은 현재 요청에서
  사용자가 NAVER를 지정하거나 해당 문서 범위의 외부 전송을 명시적으로 승인한
  경우에만 `docling-naver-ocr-v1`을 사용한다.
- 원본과 생성 bundle을 직접 수정하거나 덮어쓰지 않는다. 동일한 원본과 프로필은
  검증 후 재사용하고, 다른 조건의 결과는 새 프로필 ID 또는 별도 출력 루트에 만든다.
- 한 배치는 한 collection의 문서만 포함한다. 여러 collection을 함께 요청받으면
  collection별 배치로 나눠 각각의 출력 루트에 저장한다.

## 표준 디렉터리

원본의 첫 번째 하위 디렉터리를 collection으로 유지한다. 예를 들어
`data/raw/knowledge_docs/`의 결과는 `data/processed/docling/knowledge_docs/`에 둔다.
원본이 `data/raw/` 바로 아래에 있으면 collection은 `default`를 사용한다.

```text
data/
├── raw/
│   └── <collection>/
│       └── <source-file>
├── processed/
│   └── docling/
│       └── <collection>/
│           ├── <safe-stem>--<source-sha12>--<profile-id>/
│           │   ├── document.docling.json
│           │   ├── document.md
│           │   ├── manifest.json
│           │   └── assets/
│           ├── batches/
│           └── failures/
├── ocr/
└── indexes/
```

| 경로 또는 파일 | 역할과 규칙 |
|---|---|
| `data/raw/` | 주최측 원본이자 답변의 최종 근거다. 수정, 덮어쓰기, 포맷 변환을 금지한다. |
| `document.docling.json` | 문서 구조와 provenance를 보존하는 기계 기준 파싱 결과다. 직접 편집하지 않는다. |
| `document.md` | 사람이 읽고 검수하는 파생 결과다. 직접 보정해 기준 데이터로 사용하지 않는다. |
| `assets/` | JSON과 Markdown이 참조하는 이미지다. 이름을 바꾸거나 bundle 밖으로 옮기지 않는다. |
| `manifest.json` | 원본 SHA-256, 프로필 ID/digest, 런타임과 산출물 해시를 기록한다. 직접 편집하지 않는다. |
| batch manifest | 한 실행의 성공, 재사용, 실패, 건너뜀 항목을 기록하는 실행 원장이다. |
| `data/ocr/` | 현재 파서가 사용하지 않는 진단용 중간물 예약 경로다. 기준 결과를 두지 않는다. |
| `data/indexes/` | 이후 retrieval 단계의 재생성 가능한 결과다. 현재 작업 범위 밖이다. |

`document.docling.json`, `document.md`, `manifest.json`, `assets/`는 하나의 원자적
bundle이다. 일부만 복사하거나 공유하지 않는다. 실제 데이터와 생성 결과는 Git에
커밋하지 않는다.

## 저장소와 파서 프로젝트 찾기

Skill의 위치에서 상위 디렉터리를 탐색해 다음 두 파일이 모두 있는 가장 가까운
디렉터리를 `<repo-root>`로 정한다.

```text
docs/operations/document-parsing.md
tools/docling_parser/pyproject.toml
```

`<parser-project>`는 `<repo-root>/tools/docling_parser`다. 특정 사용자의 절대 경로를
명령이나 문서에 저장하지 않는다. 모든 파서 명령은 작업 디렉터리를 `<repo-root>`로
설정하고 실행한다. 이 조건은 기본 허용 경로를 저장소 안으로 제한한다.

원본은 가능하면 `<repo-root>/data/raw/<collection>`에 읽기 전용으로 복사해 관리한다.
기존 외부 원본을 제자리에서 읽어야 하면 출력 경로는 저장소 안에 유지한 채
`DOCLING_PARSER_ALLOWED_ROOTS`에 `<repo-root>`와 `<external-source-root>`만 추가한다.
이때 `<external-source-root>`는 공통 상위 데이터 폴더가 아니라 한 collection의
디렉터리로 정하고, 그 디렉터리 이름을 `<collection>`으로 사용한다. 여러 외부
collection은 각각 별도 허용 루트와 별도 배치로 처리한다.
macOS/WSL에서는 `:`, Windows에서는 `;`로 구분한다. 상위 작업공간 전체처럼 필요한
범위보다 넓은 경로를 허용하지 않는다. 예를 들어 macOS/WSL의 임시 셸 설정은 다음과
같다.

```bash
export DOCLING_PARSER_ALLOWED_ROOTS="<repo-root>:<external-source-root>"
```

반복 사용할 값은 커밋되지 않는 `<repo-root>/.env.parser`에 저장할 수 있다. 로컬 OCR
명령에서도 `docling-parser` 앞에 `--env-file "<repo-root>/.env.parser"`를 추가해야 그
파일을 읽는다.

최초 한 번 의존성을 설치한다.

```bash
uv sync --locked --project "<parser-project>"
```

파서 프로젝트의 `.python-version`이 로컬과 CI의 Python 3.12를 고정한다. 루트 API
환경과 파서 가상환경을 섞지 않는다.

EasyOCR와 Docling 모델은 첫 로컬 파싱에서 추가로 다운로드될 수 있다. 로컬 실행
전에는 다음 두 명령으로 환경과 고정 프로필을 확인한다. `make parser-doctor`는 첫
명령과 같은 로컬 점검용이다.

```bash
uv run --frozen --project "<parser-project>" docling-parser doctor
uv run --frozen --project "<parser-project>" docling-parser profiles
```

## 로컬 OCR 실행

로컬 OCR을 기본으로 사용한다. 외부 전송이 없고 Windows x64, WSL x64, macOS Apple
Silicon에서 같은 EasyOCR `ko`/`en`, CPU 프로필을 사용할 수 있기 때문이다.

파일 하나:

```bash
uv run --frozen --project "<parser-project>" docling-parser parse-local \
  "<source-path>" \
  --output-dir "<repo-root>/data/processed/docling/<collection>" \
  --conflict-policy reuse_identical
```

명시한 파일 여러 개:

```bash
uv run --frozen --project "<parser-project>" docling-parser batch-local \
  --source-path "<first-source-path>" \
  --source-path "<second-source-path>" \
  --output-dir "<repo-root>/data/processed/docling/<collection>" \
  --failure-policy continue \
  --conflict-policy reuse_identical
```

collection 폴더 전체:

```bash
uv run --frozen --project "<parser-project>" docling-parser batch-local \
  --source-dir "<repo-root>/data/raw/<collection>" \
  --recursive \
  --output-dir "<repo-root>/data/processed/docling/<collection>" \
  --failure-policy continue \
  --conflict-policy reuse_identical
```

로컬 배치는 실패 문서를 한 번에 확인할 수 있도록 `continue`를 표준으로 사용한다.

## NAVER OCR 실행

NAVER OCR은 렌더링된 문서 이미지 또는 이미지 영역과 Office 내장 이미지를 NAVER
Cloud로 전송하고 호출 비용이 발생할 수 있다. 현재 요청의 승인 범위가 파일인지
폴더인지 확인하고, 배치에서는 실행 전에 대상 파일 목록과 개수를 확인한다. 이전
대화의 승인, 환경 변수 또는 자격 증명의 존재만으로 동의를 추론하지 않는다.

`tools/docling_parser/.env.example`을 `<repo-root>/.env.parser`로 복사한 뒤 다음 값을
실행 환경 또는 그 파일에만 둔다. 제품 런타임의 `.env`를 통째로 파서에 전달하지
않는다. 외부 원본을 읽는 경우에만 앞에서 설명한 최소 허용 루트도 이 파일에 추가한다.

```text
DOCLING_PARSER_ENABLE_NAVER_OCR=true
NAVER_OCR_INVOKE_URL=<General OCR Invoke URL>
NAVER_OCR_SECRET=<X-OCR-SECRET>
```

실제 값을 명령행, Skill, 문서, 로그, manifest 또는 프롬프트에 넣거나 표시하지
않는다. `.env.parser`는 Git ignore 및 pre-commit 차단 대상이다. 파일을 사용할 때만
`uv run`에 다음 옵션을 추가한다.

```bash
--env-file "<repo-root>/.env.parser"
```

NAVER 실행 전 실제 실행과 같은 환경으로 점검한다.

```bash
uv run --frozen --project "<parser-project>" \
  --env-file "<repo-root>/.env.parser" \
  docling-parser doctor
uv run --frozen --project "<parser-project>" \
  --env-file "<repo-root>/.env.parser" \
  docling-parser profiles
```

파일 하나:

```bash
uv run --frozen --project "<parser-project>" \
  --env-file "<repo-root>/.env.parser" \
  docling-parser parse-naver "<source-path>" \
  --confirm-external-transfer \
  --output-dir "<repo-root>/data/processed/docling/<collection>" \
  --conflict-policy reuse_identical
```

명시한 파일 여러 개:

```bash
uv run --frozen --project "<parser-project>" \
  --env-file "<repo-root>/.env.parser" \
  docling-parser batch-naver \
  --source-path "<first-source-path>" \
  --source-path "<second-source-path>" \
  --confirm-external-transfer \
  --output-dir "<repo-root>/data/processed/docling/<collection>" \
  --failure-policy stop \
  --conflict-policy reuse_identical
```

collection 폴더 전체:

```bash
uv run --frozen --project "<parser-project>" \
  --env-file "<repo-root>/.env.parser" \
  docling-parser batch-naver \
  --source-dir "<repo-root>/data/raw/<collection>" \
  --recursive \
  --confirm-external-transfer \
  --output-dir "<repo-root>/data/processed/docling/<collection>" \
  --failure-policy stop \
  --conflict-policy reuse_identical
```

NAVER 배치는 연속 실패와 불필요한 비용을 제한하기 위해 `stop`을 표준으로 사용한다.
NAVER 호출이 최종 실패하면 문서 전체를 실패 처리하며 로컬 OCR로 자동 대체하지
않는다. `.env.parser`가 없고 필요한 변수가 이미 프로세스 환경에 있으면 `--env-file`만
생략한다.

## 재사용, 충돌과 프로필 변경

- 표준 실행은 `reuse_identical`을 사용한다. 원본 SHA-256, 프로필 digest와 기존
  산출물 해시가 모두 맞을 때만 결과를 재사용한다.
- 자동 삭제와 덮어쓰기는 금지한다. 비교 결과가 필요하면 별도 출력 루트를 사용한다.
- Docling 버전, 파서 코드, 모델 또는 설정 변경이 결과에 영향을 줄 수 있으면 기존
  프로필 ID의 내용을 바꾸지 말고 `-v2`처럼 새 ID를 만든다.
- `reuse_identical`은 파서 코드 변경 자체를 동등성 조건으로 사용하지 않는다. 따라서
  결과 의미가 바뀌는 코드 변경도 프로필 버전을 올려야 한다.
- Markdown 또는 JSON을 사람이 수정한 bundle은 재사용하거나 downstream에 넘기지
  않고 원본에서 다시 파싱한다.

## 결과와 실패 판정

CLI의 표준 출력 JSON과 종료 코드를 함께 확인한다.

- 단일 문서는 `status`가 `success` 또는 `reused`이고 manifest와 모든 산출물 해시가
  존재할 때 기술적으로 성공이다. `reused`는 CLI가 기존 manifest와 산출물 해시를
  다시 검증한 정상 결과다.
- 배치가 `failed` 또는 `partial_success`이면 일부 bundle이 생성됐더라도 corpus
  준비 완료로 보고하지 않는다.
- `failed=0`, `skipped=0`이고 모든 항목이 `success` 또는 `reused`이면 배치는 기술적으로
  완료된 것이다. 이는 사람 검수 완료를 의미하지 않는다.
- 경고는 실패는 아니지만 검수 대상이다.
- 종료 코드 `1`이어도 표준 출력에 batch JSON이 있을 수 있다. 구조화된 표준 오류와
  failure manifest 경로도 함께 확인한다.
- 파싱 시작 전 설정·경로 오류는 failure manifest 없이 표준 오류만 남을 수 있다.

## 사람 검수

제공 문서가 답변의 최종 근거이고 금융 문서의 숫자 오류 비용이 크므로 다음 순서로
우선 검수한다.

1. `manifest.json`의 원본 SHA-256, 프로필 ID/digest와 경고를 확인한다.
2. 페이지·슬라이드·시트의 제목과 읽기 순서를 확인한다.
3. 표의 행·열, 단위, 소수점, 음수 부호를 원본과 대조한다.
4. 세율, 한도, 날짜, 연령 조건과 각주·예외 문구를 대조한다.
5. 차트 범례와 이미지 안 문자가 Markdown에 반영됐는지 확인한다.
6. Markdown 이미지 링크가 같은 bundle의 `assets/`를 가리키는지 확인한다.

검수 메모 때문에 생성 bundle을 수정하지 않는다. 여러 실행에서 재사용할 OCR 선택
근거나 품질 비교 중 수치로 재현 가능한 실험만 `docs/experiments.md`에 기록하고 실제
문서 내용이나 민감정보는 남기지 않는다. 기술적으로 완료된 bundle도 위 필수 항목을
사람이 확인하기 전에는 후보 결과다. 검수 완료와 채택 여부는 관련 PR, 이슈 또는 팀
작업 기록에 남기며, 채택본만 후속 정규화와 retrieval 입력으로 사용한다. 채택한
bundle은 검색 인덱스 확정과 대회 평가 종료 전까지 팀 공유 artifact로 보존한다.
공유 저장소가 정해지면 bundle과 batch manifest를 통째로 이동하며, 절대 경로가
아니라 원본 SHA-256과 프로필 digest로 동일성을 판단한다.

## 운영체제 경로

- WSL 프로세스에는 `/home/...` 경로만 전달한다. `\\wsl$` 또는
  `\\wsl.localhost` 경로를 WSL Python CLI에 전달하지 않는다.
- Windows 네이티브에서는 PowerShell, Windows Python과 `C:\...` 경로를 함께
  사용한다.
- macOS에서는 POSIX 경로를 사용한다.
- Windows와 WSL의 Python 환경, 경로와 환경 변수를 섞지 않는다.
- `DOCLING_PARSER_ALLOWED_ROOTS`의 다중 경로 구분자는 Windows에서 `;`,
  macOS/WSL에서 `:`이다.
- 입력과 출력에는 symlink나 junction이 아닌 실경로를 사용한다.

## Skill 유지보수

- 실행 명령, 저장 위치, 실패 처리나 검수 정책은 이 문서에서만 변경한다.
- Skill 선택 조건이 바뀔 때만 네 `SKILL.md`의 YAML `description`을 함께 변경한다.
- Codex와 Claude Code의 같은 이름 Skill 본문은 동일하게 유지한다.
- 중앙 문서나 `tools/docling_parser/pyproject.toml`을 찾지 못하면 경로를 추측하거나
  다른 파서로 우회하지 말고 설정 오류를 보고한다.
- Git symlink나 Skill 생성 스크립트는 사용하지 않는다. Windows 호환성과 3인 팀의
  유지보수 비용을 고려해 짧은 진입점 파일만 복제한다.
