---
status: accepted
date: 2026-08-26
type: architecture
related:
  - 20260803-module-dependency-direction.md
  - 20260813-main-supervisor-domain-agent-tools.md
  - 20260825-98-domain-agent-implementation-ownership.md
supersedes: []
superseded-by: []
---

# 계산 함수를 Domain Agent와 분리된 공용 Python 모듈로 둔다

## 배경

프로젝트는 확정 수치를 LLM이 아닌 결정론적 Python 함수에서 만들도록 제한한다. 세제·수령
외에도 기준가격과 위험등급 등 여러 도메인에 계산 요구가 있지만, 현재 실제 소비 Agent와
권한·버전 정책은 정해지지 않았다.

계산 함수가 특정 Domain Agent 내부에 있으면 다른 도메인에서 재사용하기 어렵다. 반대로
현재 필요하지 않은 Registry lifecycle, adapter, 권한과 기간 정책까지 미리 구현하면 단순한
산식 추가가 공용 프레임워크 변경으로 커진다.

## 결정

검증된 계산 함수는 `pension_agent/rules/`가 소유한다. 공용 진입점은
`calculate(CalculationRequest)` 함수 하나이며, 계산기 ID는 정적 `CALCULATORS` 딕셔너리의
Pydantic 입력 모델과 Python 함수에 연결한다.

문자열 수식, DSL, `eval`, 동적 등록과 동적 import는 지원하지 않는다. 현재 계산기에서
사용하지 않는 lifecycle, 다중 버전, 적용 기간, permission과 Agent adapter도 구현하지
않는다. 이러한 요구가 실제로 생기면 소비자 이슈에서 최소 계약을 추가한다.

계산 결과에는 정규화 입력, 출력, 단위와 warning만 포함한다. 계산 출처와 parser
provenance는 오프라인 개발 자료로 관리하고 런타임 결과나 Agent 근거에 포함하지 않는다.

## 고려한 대안

### Domain Agent별 계산 함수

첫 사용은 단순하지만 동일한 입력 검증과 Decimal 규칙이 여러 Agent에 중복된다.

### 범용 Registry와 adapter 계층

버전·기간·권한 정책을 중앙화할 수 있지만 현재 실제 사용 사례가 없어 코드와 오류 계약만
늘어난다. 필요한 정책은 Agent 연결 시점에 추가하는 편이 변경 범위를 명확히 한다.

### 계산식 문자열 실행기

함수 추가는 빠르지만 검증되지 않은 식을 실행할 수 있어 채택하지 않는다.

## 결과

- 계산 함수와 Agent 구현의 의존성을 분리한다.
- 계산기 추가는 입력 모델, 순수 함수와 `CALCULATORS` 한 항목으로 제한된다.
- 버전·기간·권한·근거 연결은 실제 소비자가 생길 때 별도 결정한다.
- Agent 연결 전에는 외부 API와 `DomainResult.calculations` 동작이 바뀌지 않는다.

## 관련 자료

- [GitHub 이슈 #104](https://github.com/nayeon653/-ace3/issues/104)
- [Calculation Service 스펙](../specs/components/calculation-service.md)
