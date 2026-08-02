---
status: accepted
date: 2026-08-03
type: architecture
related:
  - 20260802-ace-4-package-layout.md
  - 20260803-api-interface-module.md
supersedes: []
superseded-by: []
---

# 모듈 의존성 방향을 단방향으로 제한

## 배경

실행 코드를 하나의 패키지로 통합했지만 import 방향을 정하지 않으면 FastAPI,
문서 파싱 라이브러리나 에이전트 오케스트레이션이 검색·계산 모듈로 역류할 수 있다.
특히 운영 경로가 `ingest`를 import하면 오프라인 파싱 의존성이 운영 환경에 섞인다.

## 결정

내부 모듈의 허용 의존성을 다음과 같이 제한한다.

| 모듈 | import 가능한 내부 모듈 |
|---|---|
| `core` | 없음 |
| `config` | `core` |
| `rules` | `core`, `config` |
| `retrieval` | `core`, `config` |
| `ingest` | `core`, `config`, `retrieval` |
| `agent` | `core`, `config`, `retrieval`, `rules`, `prompts` |
| `api` | `core`, `config`, `agent` |

추가 원칙은 다음과 같다.

- `core`에는 공용 타입·프로토콜·예외만 둔다.
- `config`는 설정 로딩과 기본값을 소유한다.
- `prompts`는 다른 기능 모듈을 import하지 않는 리소스 패키지로 유지한다.
- `api`는 검색과 규칙을 직접 호출하지 않고 `agent`를 통해 사용한다.
- `api`, `agent`, `retrieval`, `rules`는 `ingest`와 파싱 라이브러리를 import하지 않는다.
- 파싱 라이브러리는 `ingest` 구현과 함께 별도 의존성 그룹으로 추가한다.
- `evals`와 `tests`는 검증 목적상 모든 모듈을 import할 수 있다.

## 고려한 대안

- 각 모듈이 필요한 기능을 직접 import하도록 두면 초기 구현은 빠르지만 순환 의존과
  전송·파싱 기술의 결합을 뒤늦게 해소해야 하므로 채택하지 않았다.
- 별도의 `domain/`, `services/`, `ports/` 계층을 지금 추가하는 방안은 현재 기능과
  팀 규모에 비해 추상화가 앞서가므로 보류했다.

## 결과

- FastAPI와 파싱 라이브러리를 교체하거나 제외해도 검색·규칙 모듈에 미치는 영향이
  제한된다.
- 단위 테스트에서 HTTP 서버나 파싱 모델 없이 도메인 모듈을 실행할 수 있다.
- 새 import를 추가할 때 허용 표를 확인해야 하며, 예외가 필요하면 결정 기록을 먼저
  갱신해야 한다.
- 구현이 늘어나면 import 경계를 CI에서 자동 검사하는 도구 도입을 재검토한다.

## 관련 자료

- [실행 패키지 구조 결정](20260802-ace-4-package-layout.md)
- [API 인터페이스 모듈 결정](20260803-api-interface-module.md)
