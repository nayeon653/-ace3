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

# 계산 기반을 Domain Agent와 분리된 공용 Python 컴포넌트로 둔다

## 배경

프로젝트는 확정 수치를 LLM이 아닌 결정론적 Python 함수에서 만들도록 제한한다. 최초 계산
요구는 세제·수령 질문에서 드러났지만 추출 카탈로그에는 기준가격, 비용, 위험등급과 운용
한도 등 여러 도메인의 계산 규칙이 함께 있다.

Calculation Service를 Tax/Payout Agent 내부에 구현하면 Product나 Policy에서 같은 실행·
검증·provenance 계약을 재사용하기 어렵다. 반대로 모든 Agent에 범용 수식 실행 Tool을
노출하면 잘못된 규칙 선택과 임의 수식 실행 위험이 생긴다.

## 결정

Calculation Service와 함수 Registry는 `pension_agent/rules/`가 소유하는 공용 결정론적
Python 컴포넌트로 구현한다. 이 패키지는 Agent를 import하지 않고 어느 Agent에도 직접
연결되지 않는다.

Registry는 사람이 원문을 검토해 active로 승인한 명시적 Python callable만 실행한다.
문자열 수식, DSL과 `eval`은 지원하지 않는다. 계산 결과에는 입력·출력뿐 아니라 계산기
버전, 도메인 태그와 원문 provenance를 포함한다.

Tax/Payout, Product와 Policy의 소비 여부와 `allowed_permissions`는 실제 사용 사례를 확인한
후 도메인별 adapter 이슈에서 결정한다. permission은 계산 요청 payload가 아니라 신뢰된
adapter 호출 경계에서 주입한다. Main Supervisor는 Calculation Service를 직접 호출하지
않는다.

## 고려한 대안

### Tax/Payout Agent 전용 계산 Tool

첫 사용 사례에는 단순하지만 계산 기반의 소유권이 Tax/Payout에 고정되고 Product 계산기를
추가할 때 의존성이 역전된다.

### Agent가 계산식 문자열을 전달하는 범용 실행기

함수 추가는 빠르지만 LLM이 검증되지 않은 식이나 다른 도메인의 규칙을 실행할 수 있다.
출처·버전·입력 경계도 함수별로 강제하기 어렵다.

### Agent별 독립 계산 코드

도메인 결합은 적지만 Registry, Decimal, 오류와 provenance 계약이 중복되고 결과 형식이
달라진다.

## 결과

- 계산 함수와 Agent adapter를 독립적으로 개발·검토할 수 있다.
- 같은 실행·버전·출처 계약을 여러 도메인이 재사용할 수 있다.
- 소비 권한은 후속 adapter에서 최소 `allowed_permissions`로 제한할 수 있다.
- 실제 소비자가 아직 없으므로 초기 Service는 단위 테스트와 직접 Python 호출로만 검증된다.
- Agent 연결 전에는 외부 API의 계산 기능이나 `DomainResult.calculations` 동작이 바뀌지 않는다.

## 관련 자료

- [GitHub 이슈 #104](https://github.com/nayeon653/-ace3/issues/104)
- [Calculation Service 스펙](../specs/components/calculation-service.md)
