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

# HTTP 인터페이스 모듈명을 `api`로 지정

## 배경

ACE-4의 패키지 구조를 적용하면서 FastAPI 진입점을 `pension_agent/server/`에 두었다.
그러나 실제 서버 프로세스와 소켓 수명주기는 Uvicorn이 담당하며, 애플리케이션 코드의
책임은 `/answer` 라우트, 요청·응답 스키마, 의존성 조립과 HTTP 예외 변환이다.

현재 프로젝트는 HTTP 외 프로토콜 서버나 백그라운드 워커를 이 모듈에서 운영할
계획이 없으므로 `server`는 책임 범위를 실제보다 넓게 표현한다.

## 결정

- FastAPI 인터페이스 계층의 패키지명을 `pension_agent/api/`로 사용한다.
- FastAPI 앱 진입점은 `pension_agent.api.app:app`으로 정의한다.
- 라우트, HTTP 스키마, 의존성 조립과 도메인 예외의 HTTP 변환을 이 계층에 둔다.
- 에이전트 흐름, 검색과 계산 규칙은 FastAPI에 의존하지 않도록 각각의 도메인
  모듈에 유지한다.
- Uvicorn 실행·컨테이너·배포 설정은 `api/`가 아니라 `infra/`와 실행 명령에서
  관리한다.

## 고려한 대안

- `server/`는 서버 실행과 수명주기까지 애플리케이션이 소유할 때 적합하지만,
  현재 FastAPI 어댑터의 역할보다 의미가 넓어 채택하지 않았다.
- `web/`은 UI나 정적 자산까지 포함하는 것으로 오해될 수 있어 선택하지 않았다.

## 결과

- 패키지명이 HTTP 인터페이스라는 실제 책임을 직접 드러낸다.
- `agent`, `retrieval`, `rules`는 전송 계층과 분리되어 HTTP 없이 테스트할 수 있다.
- HTTP 외 인터페이스가 추가되면 해당 어댑터를 별도 패키지로 추가할 수 있다.
- 기존 `pension_agent.server` import와 실행 경로는 `pension_agent.api`로 변경해야 한다.

## 관련 자료

- [선행 결정: 실행 코드를 최상위 `pension_agent` 패키지로 통합](20260802-ace-4-package-layout.md)
- [후속 결정: 모듈 의존성 방향을 단방향으로 제한](20260803-module-dependency-direction.md)
- `docs/api-spec.md`
