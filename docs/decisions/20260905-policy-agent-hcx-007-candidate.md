---
status: proposed
date: 2026-09-05
type: architecture
related:
  - 20260820-80-router-search-service.md
  - 20260824-96-selective-hcx-007-models.md
supersedes: []
superseded-by: []
---

# Policy Agent에 HCX-007 비추론 모델을 분리 적용하는 후보

## 배경

Policy Agent의 제도 비교와 계좌 운용 질문을 점검하는 과정에서 검색 계층이 질문에 직접
답하는 청크를 반환했는데도, Agent가 사용자가 요청한 비교 항목 일부를 결론에서 누락하거나
적용 조건이 다른 후보 청크까지 근거로 선택하는 사례가 확인됐다. 이 유형은 라우팅 실패나
검색 결과 부재만으로 설명되지 않고, 검색 이후 Tool 호출과 근거 선별·요약 단계의 지시
이행 성능을 별도로 확인해야 한다.

기존 역할별 모델 결정은 Main Supervisor와 Product ReAct에만 HCX-007을 사용하고 Policy,
Tax/Payout과 Product Catalog Planner에는 HCX-005를 사용한다. Policy의 판단 품질을 먼저
분리 검증하기 위해 다른 역할과 검색 설정을 함께 바꾸지 않는 모델 후보가 필요하다.

## 결정

Policy Agent 전용 `ChatClovaXConfig`와 모델 인스턴스를 만들고 `HCX-007` 비추론 모드를
주입한다. temperature, 최대 토큰, timeout과 retry는 기존 역할 설정과 동일하게 유지한다.
Function Calling 경로의 불필요한 지연과 비용을 늘리지 않도록 Thinking은 `none`으로
고정한다.

Tax/Payout Agent와 Product Catalog Planner는 계속 `HCX-005`를 사용한다. 모든 역할은 기존과
같이 런타임 소유 HTTP client와 프로세스 단위 HCX 동시성 제한을 공유한다. 이 분리는 검색,
프롬프트와 다른 Domain 모델을 고정한 상태에서 Policy 모델 변경의 영향만 확인하기 위한
것이다.

이 기록은 후보 제안이며 기존 역할별 모델 결정을 아직 대체하지 않는다. 반복 검증에서
품질 기준을 충족한 뒤에만 이 기록을 채택하고, 기존 결정의 supersede 연결과
`PROJECT_RULES.md`의 현재 모델 규칙을 함께 갱신한다.

## 고려한 대안

- 모든 Domain Agent를 HCX-007로 올리면 구성이 단순하지만 비용 영향이 넓고 어떤 역할의
  변화가 결과를 개선했는지 분리할 수 없어 제외했다.
- HCX-005 실패 시에만 HCX-007로 재시도하면 평균 비용을 줄일 수 있지만, 근거 누락이나
  과도한 근거 선택을 실행 중에 신뢰성 있게 판정할 별도 기준이 필요하고 실행 분기도
  늘어나므로 이번 후보에 포함하지 않았다.
- 프롬프트만 먼저 수정할 수도 있지만, 모델의 지시 이행 성능과 프롬프트 문제를 분리하기
  위해 이번 후보에서는 프롬프트와 검색 계층을 고정한다. 모델만으로 해결되지 않는 문제는
  후속 프롬프트 변경에서 다룬다.

## 결과

- Policy의 검색 Tool 호출, 직접 적용 가능한 근거 선택과 다항목 질문의 결론 작성 성능을
  다른 역할의 비용 증가 없이 확인할 수 있다.
- 전용 config로 역할 경계가 명시되어 Tax/Payout과 Catalog Planner가 의도치 않게
  HCX-007로 바뀌는 것을 방지한다.
- HCX-007 호출 비용과 지연이 Policy 요청에 추가될 수 있으며, 모델 상향만으로 품질 개선을
  보장하지 않는다.

채택 전에는 대표 Policy 질문을 각각 3회 이상 반복해 다음을 확인한다.

1. 비교 질문의 모든 요청 항목을 근거와 함께 결론에 반영한다.
2. 사용자 조건에 직접 적용되는 청크만 근거로 선택한다.
3. 적용 조건이 질문에 없으면 `conditional`과 구체적인 `missing_conditions`를 제출한다.
4. HTTP 응답 계약, 지연시간과 다른 Domain Agent의 동작에 회귀가 없다.

## 관련 자료

- [PR #151](https://github.com/nayeon653/-ace3/pull/151)
- [Policy Agent 스펙](../specs/agents/policy-agent.md)
