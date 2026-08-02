---
status: accepted
date: 2026-08-02
type: architecture
related:
  - https://app.notion.com/p/3ac8385edd5081fe9198cc937641db63
supersedes: []
superseded-by: []
---

# 실행 코드를 최상위 `pension_agent` 패키지로 통합

## 배경

기존 스캐폴딩은 `agent/`, `ingest/`, `index/`, `rules/`, `server/` 등 실행 코드가
저장소 최상위에 분산되어 있었다. 이 구조에서는 하나의 제품에 속하는 코드의
경계, 공용 코드의 위치, 패키징과 배포 범위가 명확하지 않다.

구현이 거의 시작되지 않아 import 경로와 실행 명령을 낮은 비용으로 변경할 수 있는
시점이었다.

## 결정

- 실행 코드를 최상위 `pension_agent/` Python 패키지로 통합한다.
- `index/`는 인덱싱과 검색을 함께 표현하도록 `pension_agent/retrieval/`로 바꾼다.
- 공용 모델·설정 로더·예외는 `pension_agent/core/`에 둔다.
- 기본 설정과 프롬프트는 실행 패키지 안에 두어 빌드 결과에 포함한다.
- 테스트, 평가, 문서, 인프라는 각각 `tests/`, `evals/`, `docs/`, `infra/`에 둔다.
- 현재는 `src/`를 도입하지 않고, 빌드 설정에 평면 패키지 구조를 명시한다.
- 의존성과 도구 설정은 `pyproject.toml`, 잠금 버전은 `uv.lock`으로 관리한다.

## 고려한 대안

- 최상위 다중 폴더 구조는 이동 비용이 없지만 실행 코드와 지원 파일의 경계 및
  패키징 기준이 계속 모호하므로 채택하지 않았다.
- `src/pension_agent/`는 저장소 루트에서 우연히 import되는 문제를 더 엄격하게
  차단하지만, 단기 3인 서비스 프로젝트에서 추가되는 경로와 학습 비용을 고려해
  보류했다.

## 결과

- 모든 실행 코드가 `pension_agent.*` import 경로를 사용한다.
- 빌드한 wheel을 저장소 밖에서 설치해도 패키지와 런타임 리소스를 import할 수 있다.
- 기존 최상위 모듈 경로를 전제로 작성한 코드는 새 경로로 수정해야 한다.
- 재사용 라이브러리 배포나 더 엄격한 import 격리가 필요해지면 `src/` 구조를
  다시 검토한다.

## 관련 자료

- [ACE-4: 실행 코드와 지원 파일을 분리하는 프로젝트 구조로 변경 검토](https://app.notion.com/p/3ac8385edd5081fe9198cc937641db63)
- `pyproject.toml`
- `.github/workflows/ci.yml`
