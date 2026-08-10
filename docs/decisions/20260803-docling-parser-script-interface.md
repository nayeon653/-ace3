---
status: accepted
date: 2026-08-03
type: architecture
related:
  - 20260803-docling-parser-operations.md
supersedes: []
superseded-by: []
---

# Docling 파서 실행 계층을 단일 Python 스크립트로 단순화

## 배경

초기 구현은 설치형 console 명령, 요청·결과 모델, 허용 경로 설정, 환경 진단,
재사용 검증과 배치 원장을 함께 제공했다. 현재 단계의 목표는 문서 파싱 결과를 사람이
검수하는 것이며 장기 실행 서비스나 원격 호출 계약은 필요하지 않다. 이 운영 계층이
NAVER OCR Docling 플러그인과 실제 파싱 로직보다 커져 코드 검토와 변경을 어렵게 했다.

## 결정

- 저장소의 `scripts/parse_document.py`를 단일 실행 진입점으로 사용한다.
- 한 번에 문서 하나만 처리하고 OCR provider와 출력 경로만 실행 인자로 받는다.
- 여러 파일 실행 순서와 실패 정책은 중앙 운영 문서를 읽은 Skill이 조정한다.
- 설치형 `docling-parser` console 명령, doctor, 내부 batch API와 별도 서비스 계층은
  제공하지 않는다.
- NAVER OCR의 Docling plugin entry point, 고정 프로필, Office 내장 이미지 OCR,
  문서별 원자적 bundle과 실패 시 무결성은 유지한다.
- 파서의 독립 `pyproject.toml`과 잠금 환경은 Docling plugin 등록과 제품 런타임
  의존성 격리를 위해 유지한다.

## 고려한 대안

- 기존 CLI를 축소해 유지하는 방식은 argparse 함수와 설치 entry point를 안정된
  외부 계약으로 계속 관리해야 하므로 현재 필요보다 크다.
- Skill 안에 파싱 Python 코드를 직접 넣으면 Codex와 Claude Code 사본 및 운영 정책이
  다시 분산되므로 채택하지 않았다.
- MCP 서버는 여러 프로세스나 원격 사용자가 공유하는 서비스 수명주기가 생길 때까지
  도입을 미룬다.

## 결과

- 개발자와 코딩 에이전트는 같은 저장소 스크립트와 고정 환경을 사용한다.
- 핵심 파싱·OCR 구현은 Python 모듈로 남아 단위 테스트할 수 있다.
- 자동 재사용, 배치 manifest와 failure manifest는 더 이상 제공하지 않는다.
- 출력 충돌은 덮어쓰지 않고 실패하며 기존 bundle을 자동 재사용할지 판정하지
  않는다.
- 향후 GUI, scheduler, 원격 worker처럼 여러 호출자가 안정된 API를 필요로 하면 이
  결정을 다시 검토하고 MCP나 작업 API를 얇게 추가한다.

## 관련 자료

- `tools/docling_parser/scripts/parse_document.py`
- `docs/operations/document-parsing.md`
