# 문서 파싱 운영 정책

이 문서는 `-ace3`의 Docling 파싱 실행, 결과 저장, 외부 OCR, 실패 처리와 검수
정책의 **유일한 원본**이다. `.agents/skills/`와 `.claude/skills/`의 Skill은 이 문서를
찾아 읽게 하는 얇은 진입점이며 명령과 정책을 복제하지 않는다.

## 범위와 원칙

- 현재 범위는 PDF, DOCX, PPTX, XLSX를 Docling으로 파싱해 문서별 artifact bundle을
  만드는 단계까지다. 청킹, 임베딩과 검색 인덱스 생성은 포함하지 않는다.
- 파서는 `tools/docling_parser/`의 독립 Python 환경에서 저장소 스크립트로 실행한다.
  평가 API와 `pension_agent` 런타임에서는 파서 패키지를 import하지 않는다.
- 일반 요청에는 `docling-local-ocr-v1`을 사용한다. NAVER OCR을 사용자가 현재
  요청에서 지정하거나 해당 범위의 외부 전송을 승인한 경우에만
  `docling-naver-ocr-v1`을 사용한다.
- 원본과 생성 bundle을 수정하거나 덮어쓰지 않는다. 비교가 필요하면 별도 출력
  루트에 다시 생성한다.
- Docling JSON을 기계 기준 결과로 사용하고 Markdown을 사람 검수용 표현으로
  사용한다. 특히 병합 셀이 있는 표는 Markdown에서 값이 반복되거나 span 정보가
  평탄화될 수 있으므로 후속 청킹은 JSON의 행·열·span을 기준으로 한다.
- 여러 페이지의 같은 여백 위치에 반복되는 작은 그림은 머리말·꼬리말 장식으로
  판정해 bundle에서 제외한다. 남은 내장 그림의 OCR 텍스트와 좌표는 Docling JSON에
  보존하되, 의미 관계가 사라진 토큰 나열이 검색 본문을 오염시키지 않도록 Markdown의
  기본 body layer에서는 제외한다. 전체 페이지 스캔 그림의 OCR 텍스트는 제외하지
  않는다.
- PDF 페이지 아래에서 끝나고 다음 페이지 위에서 같은 열 수와 수평 폭으로 이어지며,
  다음 표 앞에 별도 제목이나 본문이 없는 표는 잠재적인 페이지 간 연속 표로
  판정한다. 방향과 구조가 호환되는 고신뢰 표는 하나의 `TableItem`으로 병합하고,
  정확히 반복되는 머리글과 빈 선두 열로 시작하는 연속 행을 정리한다. 원본 segment의
  페이지·행 범위·제거한 머리글과 연속 행 정보는 manifest의 `quality_signals`에
  기록한다. 안전 조건을 충족하지 못한 후보는 합치지 않고 경고만 남긴다. XLSX 시트
  경계에는 이 판정과 병합을 적용하지 않는다.

## 표준 디렉터리와 bundle

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
│           └── <safe-stem>--<source-sha12>--<profile-id>/
│               ├── document.docling.json
│               ├── document.md
│               ├── document.html
│               ├── manifest.json
│               └── assets/
├── ocr/
└── indexes/
```

| 경로 또는 파일 | 역할과 규칙 |
|---|---|
| `data/raw/` | 원본이자 답변의 최종 근거다. 수정하거나 덮어쓰지 않는다. |
| `document.docling.json` | 문서 구조와 provenance를 보존하는 기계 기준 결과다. 직접 편집하지 않는다. |
| `document.md` | 사람이 읽고 검수하는 파생 결과다. 직접 보정해 기준 데이터로 만들지 않는다. |
| `document.html` | 표의 행·열 병합을 표현하고 이미지를 파일 안에 포함한 사람 검수용 파생 결과다. 고신뢰 페이지 간 연속 표는 하나의 표로 표현한다. |
| `assets/` | JSON과 Markdown이 참조하는 이미지다. bundle 밖으로 옮기거나 이름을 바꾸지 않는다. |
| `manifest.json` | 원본, 프로필, 런타임, OCR 사용량, 품질 신호와 각 산출물의 SHA-256을 기록한다. 직접 편집하지 않는다. |
| `data/ocr/` | 현재 사용하지 않는 진단용 중간물 예약 경로다. |
| `data/indexes/` | 후속 retrieval 단계의 재생성 가능한 결과다. 현재 범위 밖이다. |

다섯 산출물은 하나의 원자적 bundle이다. 일부만 복사하거나 공유하지 않는다. 실제
원본과 생성 결과는 Git에 커밋하지 않는다.

## 저장소와 실행 스크립트 찾기

Skill의 위치에서 상위 디렉터리를 탐색해 다음 두 파일이 모두 있는 가장 가까운
디렉터리를 `<repo-root>`로 정한다.

```text
docs/operations/document-parsing.md
tools/docling_parser/scripts/parse_document.py
```

`<parser-project>`는 `<repo-root>/tools/docling_parser`, `<parse-script>`는
`<parser-project>/scripts/parse_document.py`다. 특정 사용자의 절대 경로를 문서나
Skill에 저장하지 않는다. 모든 명령은 작업 디렉터리를 `<repo-root>`로 설정한다.

최초 한 번 의존성을 설치한다.

```bash
uv sync --locked --project "<parser-project>"
```

파서 프로젝트의 `.python-version`과 잠금 파일이 Python 3.12 및 라이브러리 버전을
고정한다. 루트 API 환경과 파서 가상환경을 섞지 않는다. EasyOCR와 Docling 모델은
첫 로컬 파싱에서 추가로 다운로드될 수 있다.

## 로컬 OCR 실행

외부 전송이 없는 로컬 OCR을 기본으로 사용한다. 지원 문서 하나를 다음과 같이
실행한다.

```bash
uv run --frozen --project "<parser-project>" python "<parse-script>" "<source-path>" --ocr local --output-dir "<repo-root>/data/processed/docling/<collection>"
```

여러 파일이나 폴더 요청은 지원 확장자의 실제 파일 목록을 먼저 확정한 뒤 같은
명령을 파일별로 반복한다. 로컬 OCR은 한 파일이 실패해도 나머지를 계속하고 마지막에
성공·실패 파일을 요약한다. 파서 자체에 배치 상태나 별도 배치 manifest는 두지 않는다.

## NAVER OCR 실행

NAVER OCR은 렌더링된 문서 이미지나 이미지 영역과 Office 내장 이미지를 NAVER
Cloud로 전송하고 호출 비용이 발생할 수 있다. 현재 요청의 승인 범위가 파일인지
폴더인지 확인하고, 여러 파일이면 실행 전에 대상 목록과 개수를 보여준다. 이전
대화의 승인이나 자격 증명의 존재만으로 동의를 추론하지 않는다.

`tools/docling_parser/.env.example`을 커밋되지 않는 `<repo-root>/.env.parser`로
복사하고 다음 값을 실행 환경 또는 그 파일에만 둔다.

```text
NAVER_OCR_INVOKE_URL=<General OCR Invoke URL>
NAVER_OCR_SECRET=<X-OCR-SECRET>
```

실제 값을 명령행, Skill, 문서, 로그, manifest 또는 프롬프트에 넣거나 표시하지
않는다. 제품 런타임의 `.env`를 통째로 파서에 전달하지 않는다.

```bash
uv run --frozen --project "<parser-project>" --env-file "<repo-root>/.env.parser" python "<parse-script>" "<source-path>" --ocr naver --confirm-external-transfer --output-dir "<repo-root>/data/processed/docling/<collection>"
```

필요한 변수가 이미 프로세스 환경에 있으면 `--env-file`만 생략한다. 여러 파일은
파일별로 실행하되 첫 실패에서 중단한다. NAVER 호출이 최종 실패하면 해당 문서 전체를
실패 처리하며 로컬 OCR로 자동 대체하지 않는다.

성공 bundle의 manifest schema 7부터 `ocr_usage`에 `image_requests`, `api_calls`,
`cache_hits`, `cache_misses`, `retry_attempts`를 기록한다. `api_calls`는 재시도를 포함한
실제 HTTP POST 횟수이고 `image_requests`는 캐시 조회까지 도달한 논리 이미지 요청
수다. 성공한 응답만 같은 프로세스의 동일 문서 변환 중 SHA-256 기준으로 재사용한다.
호출 URL, 비밀키, 요청 ID와 이미지 해시는 manifest에 기록하지 않는다.

## 충돌, 실패와 프로필 변경

- 출력 폴더 이름은 원본 stem, 원본 SHA-256 앞 12자리와 프로필 ID로 정한다.
- 같은 출력이 이미 있으면 덮어쓰거나 자동 재사용하지 않고 `OUTPUT_EXISTS`로
  중단한다. 기존 결과를 자동 재사용할지는 현재 파서가 판정하지 않는다.
- 파싱 실패 시 완성되지 않은 임시 폴더를 제거하며 최종 bundle이나 failure manifest를
  게시하지 않는다.
- 첫 병합 전이고 해당 프로필의 bundle이 공유되거나 채택되지 않았다면 최종 구현을
  `-v1`로 정리할 수 있다. 이때 같은 ID로 만든 이전 실험 bundle은 후속 단계에서
  제외하고 다시 파싱한다.
- Docling 버전, 파서 코드, 모델 또는 설정 변경이 결과에 영향을 줄 수 있으면 기존
  프로필 ID의 내용을 바꾸지 말고 `-v2`처럼 새 ID를 만든다.
- Markdown이나 JSON을 사람이 수정한 bundle은 후속 단계에 넘기지 않고 원본에서
  다시 파싱한다.

## 결과 판정과 사람 검수

스크립트의 표준 출력 JSON과 종료 코드를 함께 확인한다. 종료 코드 `0`,
`status=success`, 완성된 manifest와 다섯 산출물 종류가 모두 있을 때 기술적으로
성공이다. 파서 실행 오류는 종료 코드 `1`과 표준 오류 JSON으로, 잘못된
명령 인자는 `argparse` 안내와 종료 코드 `2`로 반환된다. 경고는 실패는 아니지만
검수 대상이다. 기술적 성공은 사람 검수 완료를 뜻하지 않는다.

검수 순서는 다음과 같다.

1. `manifest.json`의 원본 SHA-256, 프로필 ID/digest, 경고와 NAVER 사용 시
   `ocr_usage`의 실제 API 호출·캐시·재시도 횟수를 확인한다.
2. 페이지·슬라이드·시트의 제목과 읽기 순서를 확인한다.
3. 표의 행·열, 단위, 소수점, 음수 부호를 원본과 대조한다.
4. 세율, 한도, 날짜, 연령 조건과 각주·예외 문구를 대조한다.
5. 차트 범례와 이미지 안 문자가 Markdown에 반영됐는지 확인한다.
6. Markdown 이미지 링크가 같은 bundle의 `assets/`를 가리키는지 확인한다.
7. HTML에서 표의 병합 셀과 내장 이미지가 깨지지 않고 표시되는지 확인한다.
8. `merged_multipage_tables`의 페이지와 행 범위를 원본의 페이지 경계와 대조한다.

검수 메모 때문에 생성 bundle을 수정하지 않는다. 사람이 확인하기 전에는 검수 전
결과로 취급한다. 공유 저장 위치, 검수 상태 기록 방식과 후속 정규화·retrieval 입력
선정 기준은 팀 합의 후 별도 운영 정책으로 반영한다.

## 운영체제 경로

- WSL 프로세스에는 `/home/...` 경로만 전달한다. `\\wsl$` 또는
  `\\wsl.localhost` 경로를 WSL Python에 전달하지 않는다.
- Windows 네이티브에서는 PowerShell, Windows Python과 `C:\...` 경로를 함께
  사용한다.
- macOS에서는 POSIX 경로를 사용한다.
- Windows와 WSL의 Python 환경, 경로와 환경 변수를 섞지 않는다.
- 입력과 출력에 symlink나 junction을 사용하면 파서가 거부한다.

## Skill 유지보수

- 실행 명령, 저장 위치, 실패 처리와 검수 정책은 이 문서에서만 변경한다.
- Skill 선택 조건이나 중앙 파일 위치가 바뀔 때만 네 `SKILL.md`를 함께 변경한다.
- Codex와 Claude Code의 같은 이름 Skill 본문은 동일하게 유지한다.
- 중앙 문서나 `tools/docling_parser/scripts/parse_document.py`를 찾지 못하면 경로를
  추측하거나 다른 파서로 우회하지 말고 설정 오류를 보고한다.
- Windows 호환성을 위해 Git symlink를 사용하지 않고 짧은 진입점 파일만 복제한다.
