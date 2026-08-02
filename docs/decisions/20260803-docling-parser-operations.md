---
status: accepted
date: 2026-08-03
type: architecture
related:
  - 20260802-ace-4-package-layout.md
  - 20260803-module-dependency-direction.md
supersedes: []
superseded-by: []
---

# Docling 파서를 독립 오프라인 도구와 중앙 운영 정책으로 관리

## 배경

제공 문서가 답변의 최종 근거이므로 파싱 결과에는 표·숫자·이미지 문자와 원본
provenance가 보존되어야 한다. 팀원이 Windows, WSL, macOS에서 같은 파싱 조건을
사용하고 Codex와 Claude Code도 같은 절차를 실행할 수 있어야 한다.

Docling 파서는 NumPy 1.x, PyTorch와 대형 모델 의존성을 사용하지만 평가 API의 현재
환경은 NumPy 2.x이며 파싱 기능은 온라인 요청 경로에서 실행하지 않는다. 파서를
애플리케이션 환경에 합치면 API 배포 크기와 의존성 충돌 위험이 늘어난다. 반대로
Codex/Claude Skill에 전체 명령과 정책을 각각 복사하면 네 파일이 쉽게 달라진다.

## 결정

- Docling 파서를 제품 런타임이 아닌 저장소 내부 오프라인 도구로 분류하고
  `tools/docling_parser/`에 자체 `pyproject.toml`, `uv.lock`, 테스트와 함께 둔다.
- `pension_agent`와 평가 API는 파서 패키지를 import하지 않는다. 후속 ingest와
  retrieval 구현은 `data/processed/docling/`의 artifact 계약을 소비한다.
- 이 오프라인 도구는 “실행 코드를 `pension_agent`에 둔다”는 패키지 결정의 명시적
  예외다. 향후 애플리케이션 내부 파서가 필요하면 별도 의존성 그룹 원칙을 적용한다.
- 고정 로컬 EasyOCR와 NAVER CLOVA General OCR V2 프로필을 제공하되 일반 파싱은
  로컬을 기본으로 한다. NAVER는 현재 요청에서 사용자가 지정했거나 해당 범위의 외부
  전송을 명시적으로 승인한 경우에만 사용한다.
- `document.docling.json`, `document.md`, `manifest.json`, `assets/`를 하나의 원자적
  bundle로 저장하고 Docling JSON을 기계 기준 결과로 사용한다.
- 실행·저장·검수 정책은 `docs/operations/document-parsing.md` 하나에서 관리한다.
  Codex와 Claude Code의 로컬/NAVER Skill은 선택 metadata와 중앙 문서 경로만 가진다.
- 실제 원본, 파싱 결과와 검색 인덱스는 Git에 포함하지 않는다.
- 청킹, 임베딩과 인덱싱 정책은 파싱 검수가 끝난 뒤 별도 결정으로 다룬다.

## 고려한 대안

- 파서를 `pension_agent/ingest/`에 넣고 루트 dependency group으로 관리하면 기존
  패키지 결정에는 맞지만 NumPy 주버전 충돌, 약 1.6GB의 개발·CI 환경 증가와 API
  wheel의 불완전한 선택 의존성 문제가 생겨 채택하지 않았다.
- MCP 서버는 장기 실행 서비스나 원격 공유가 필요하지 않은 현재 로컬 배치 작업에
  추가 수명주기와 설정만 만들므로 채택하지 않았다.
- 네 Skill에 전체 절차를 복제하는 방식은 에이전트별 내용이 달라질 위험 때문에
  채택하지 않았다.
- Git symlink는 Windows checkout 설정에 따라 동작이 달라질 수 있어 채택하지 않았다.
- Markdown만 기준 결과로 저장하는 방식은 문서 계층, 표, 이미지 참조와 provenance를
  잃기 쉬워 채택하지 않았다.

## 결과

- API 환경과 파서 환경은 서로 다른 잠금 파일과 가상환경을 사용한다.
- 파서 경로가 바뀌는 PR은 별도 CI에서 고정 Python과 잠금 환경으로 테스트·빌드한다.
- 팀원은 저장소를 clone한 뒤 파서 프로젝트만 별도로 동기화해야 한다.
- 최초 이관은 실행 코드, 보안 회귀 테스트, 잠금 파일과 운영 계약을 분리하면 검증
  불가능한 중간 상태가 되므로 브랜치 400줄 제한의 일회성 예외로 함께 반영한다. 이후
  변경은 기존 크기 제한을 따른다.
- 루트 wheel과 Docker 이미지에는 Docling과 파서 Skill이 자동 포함되지 않는다.
- Skill 단독 복사는 중앙 문서 경로를 깨뜨리므로 저장소 전체를 배포 단위로 취급한다.
- 현재 파서 결과를 애플리케이션에서 직접 import하는 adapter는 만들지 않는다. 후속
  정규화 계약이 정해질 때 artifact 소비 경계를 `pension_agent/ingest/`에 추가한다.
- 파싱 결과에 영향을 주는 변경은 새 프로필 ID를 만들어 기존 결과의 의미를 보존한다.

## 관련 자료

- `tools/docling_parser/`
- `docs/operations/document-parsing.md`
- `data/README.md`
