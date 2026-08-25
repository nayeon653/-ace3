---
status: accepted
date: 2026-08-25
type: architecture
related:
  - 20260813-main-supervisor-domain-agent-tools.md
  - 20260820-80-router-search-service.md
  - 20260824-96-selective-hcx-007-models.md
supersedes: []
superseded-by: []
---

# 도메인 Agent 구현과 생성 책임을 각 도메인 패키지가 소유

## 배경

Policy, Tax/Payout, Product Agent는 모두 LangChain `create_agent` 기반 ReAct로 시작했다.
공통 `create_domain_agent`가 세 Agent의 state, Tool, middleware와 graph를 한 번에 만들었고,
Product 전용 카탈로그 상태와 실행 순서도 공통 모듈의 조건 분기로 처리했다.

이 구조에서는 한 도메인을 별도 LangGraph나 고정 Python workflow로 바꾸려 해도 공통
Factory와 다른 도메인의 ReAct 구성을 함께 수정해야 한다. Product가 별도 ReAct 모델과
Catalog Planner 모델을 사용하면서 공통 Factory 시그니처도 실제 의존성을 표현하지
못하게 됐다.

## 결정

공통 Agent 계층에는 다음 책임만 둔다.

1. `DomainRequest -> DomainResult` 호출 계약
2. timeout과 동시성 제한
3. 반환 결과 검증과 내부 오류 정제
4. Main Supervisor의 Domain Tool adapter

`DomainRunner` Protocol은 contracts에 두고 Main Supervisor가 도메인의 구현 방식을 알지
못하게 한다. `GuardedDomainRunner`는 주입된 `DomainRunner` 구현체에 timeout, 동시성,
결과 검증과 정제된 실패 결과를 적용한다.

Policy, Tax/Payout, Product 패키지는 각각 자신의 state schema, 검색·결과 제출 Tool,
middleware와 graph 조립을 소유한다. 현재 구현은 모두 ReAct이지만
`create_policy_agent`, `create_tax_payout_agent`, `create_product_agent`가 서로 독립적으로
구현체를 생성한다. 공통 `create_domain_agent`와 동일 생성 시그니처를 강제하던
`DomainAgentFactory`는 사용하지 않는다.

runtime은 세 생성 함수를 명시적으로 호출한다. Tool 이름과 설명을 담는 등록 정보는
실행 구현이나 Factory를 포함하지 않는다. 그래프 시각화는 운영 `DomainRunner` 계약에
`graph` 속성을 추가하지 않고, 현재 ReAct 구현체를 시각화 시점에만 조회한다.

검색은 Domain Agent가 의미 목표로 호출하는 결정론적 `SearchService`를 유지하며 별도
Search Agent를 만들지 않는다.

## 고려한 대안

### 공통 ReAct Factory 유지

중복 코드는 적지만 state, Tool과 middleware의 최소 공통분모가 계속 모든 도메인의 변경
상한이 된다. Product 조건 분기가 이미 추가됐고 실행 방식 변경 가능성을 막으므로
채택하지 않았다.

### Factory 클래스와 공통 설정 객체 도입

런타임 구현 선택이나 생성 상태를 보존해야 할 때는 유용하다. 현재는 세 생성 함수를
명시적으로 호출하면 충분하고, 도메인별로 다른 의존성을 선택적 필드로 합치게 되므로
채택하지 않았다.

### Policy와 Tax/Payout ReAct 구현 공유

현재 흐름은 유사하지만 Tax/Payout은 결정론적 계산 Tool과 고정 workflow로 발전할
가능성이 높다. 코드 유사성보다 독립 변경 가능성을 우선해 서로 import하지 않는다.

## 결과

- 한 도메인의 ReAct를 다른 graph나 Python workflow로 교체해도 Main과 다른 도메인의
  생성 코드를 변경하지 않는다.
- Product 전용 state와 실행 순서가 공통 Agent 계층에서 제거된다.
- runtime의 도메인별 모델과 의존성이 명시적으로 드러난다.
- 현재 유사한 ReAct 코드가 도메인 패키지마다 존재하므로 공통 동작 변경은 세 구현을
  각각 검토해야 한다.
- import boundary 테스트로 공통 실행 보호 계층의 구현 독립성과 도메인 간 독립성을
  검증한다.

## 관련 자료

- [GitHub 이슈 #98](https://github.com/nayeon653/-ace3/issues/98)
