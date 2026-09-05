---
status: accepted
date: 2026-09-06
type: architecture
related:
  - 20260905-product-comparison-execution-budget.md
  - 20260906-product-comparison-minimal-criteria.md
  - 20260905-all-generation-hcx-007.md
supersedes: []
superseded-by: []
---

# 비교 답변 작성을 compare_products가 소유한다

## 배경

기존 `compare_products`는 상품별 원문을 수집하고 Product ReAct가 비교 셀과 결론을
제출했다. Product 입력에는 상품 식별과 도구 호출 이력이 누적되며, 검색과 생성 책임이
여러 번의 모델 호출에 걸쳐 있었다. 셀 구조와 근거 ID 검사를 통과해도 실제 문장과 인용
원문의 의미가 어긋나는 사례가 있어 구조 통과를 답변 품질로 볼 수 없었다.

Product의 작성 직전 입력만 다시 구성하는 초안을 먼저 검토했으나, 비교 답변 자체를
도구가 완료하는 방향을 채택한다. 답변이 불안정한 현 단계에는 답변 검증 로직을 두지
않는다는 요청을 반영한다.

## 결정

`compare_products`가 상품별 문서 검색, 독립 입력 구성, HCX 비교 답변 생성까지 소유한다.
Product는 필요한 1~3개 항목을 선택하고 Catalog Planner로 상품을 식별한 뒤 도구에 위임한다.
도구 완료 후 Product ReAct를 다시 호출하거나 `submit_domain_result`에 비교 셀을 제출하지
않는다. 완성된 답변과 판단·조건·선택 근거·경고를 Product의 `DomainResult`로 반환한다.

비교 생성기는 HCX-007, Thinking `none`인 별도 역할이다. 전용 system prompt와 질문 원문,
판단 목표, 대상·항목, 상품별 검색 상태·제한, 고유 근거를 받는다. 전체 카탈로그와 이전
Product AI/Tool 메시지는 넘기지 않는다. 고유 청크의 전체 원문을 보존하고 상품별 참조
관계를 유지한다. 입력 토큰 상한·근거 제외·요약 호출은 추가하지 않는다.

답변 검증과 기본 실행 처리를 다음과 같이 구분한다.

- 비교 셀 제출, 대상×항목 완성도 산출, 셀별 인용 수 검사와 검증 후 재작성은 제거한다.
- 답변 내용, 인용의 의미, 추천의 적절성과 요청 항목 충족 여부를 판정하는 검증기는 두지 않는다.
- 상품 식별·입력 범위, 구조화 응답의 필드·타입, 실제 청크 ID 연결과 실행 상태·취소 처리는
  유지한다. 형식이 잘못되면 정제된 실패로 종료하고 내용 교정을 요청하지 않는다. 존재하지
  않는 선택 ID는 근거에서 제외하며 답변을 거절하지 않는다. 같은 ID는 첫 청크를 사용하고
  별도의 원문·출처 충돌 검사도 추가하지 않는다.
- 식별 부족에는 기존 결정론적 `comparison_result` 안내를 유지한다. 이 경로의 미확인
  셀은 생성 답변 검증에 사용하지 않는다. 검색 근거가 없으면 새 생성 호출 없이 정해진
  안내 문장을 `comparison_answer`로 반환한다.
- 단일 상품·카탈로그의 기존 제출과 다른 Domain의 계산·숫자 검증은 유지한다.

답변은 `DomainResult.comparison_answer`에 보존하며 `decision.conclusion`도 같은 본문을
사용한다. Main용 표현에는 기존 decision과 `comparison_answer_ready=true`를 넣어 본문을
중복하지 않으며, 전체 근거는 state의 DomainResult에 보존한다. AnswerService는 원래 완료 답변과 선택된 출처·조건·경고를 보존하고,
복합 질문의 다른 Domain 결과와 결정론적으로 조립한다. Main의 새 비교 문장을 채택하지 않는다.
외부 `/answer` 5필드 계약은 유지한다.

## 실행 예산

| 경계 | 이번 결정 |
|---|---|
| 생성 설정 | `PRODUCT_COMPARISON_ANSWER_HCX_CONFIG`, HCX-007, Thinking `none`, temperature `0.1` |
| 비교 생성 최대 출력 | 4096토큰 |
| 비교 생성 호출 | 논리적 1회, 내용·파싱 교정 생성 없음 |
| provider 호출 | timeout 30초, SDK retry 0회 |
| 공통 인프라 429 재시도 | 같은 deadline 안에서 최대 1회 추가 물리 호출 |
| 검색 | 확정된 2~5개 상품 각각 1회, 한 병렬 batch |
| 자동 보완 검색 | 현재 비교 경로에서는 0회 |
| 검색 마감 | `min(진입 시각 + 30초, Domain deadline - 30초)` 유지 |
| Product ReAct | 최대 5회 유지, 비교 답변 이후 재호출 없음 |
| 기존 Product / Planner 출력 | 4096 / 1024 유지 |
| Domain / API deadline | 75초 / 180초 유지 |
| 동시성 | 기존 프로세스 HCX·검색·embedding·Qdrant 제한 공유 |

논리적 생성 한 번과 인프라의 일시 오류 재시도에 따른 물리 호출 수를 구분한다.
새 생성 역할이 독자적인 무제한 호출이나 별도 시간 예산을 갖지 않는다. 30초 예약은
완료 보장이 아니며 부모 deadline·취소가 우선한다. 기존 Catalog Planner의 유일 후보·코드
불일치 교정은 상품 식별 단계의 동작으로 유지한다.

## 이전 결정과의 관계

[검색·출력 예산 결정](20260905-product-comparison-execution-budget.md) 중 검색 전용 도구,
Product 셀 제출·검증, 보완 검색과 생성 역할 부재에 관한 부분을 이번 결정으로 변경한다.
해당 기록을 당시 결정으로 보존하며, Product 출력 설정과 공통 deadline은 유지한다.
[최소 항목 결정](20260906-product-comparison-minimal-criteria.md)의 1~3개 선택 정책은 유지한다.
해당 기록의 최대 셀 수는 당시 제출 형식의 설명이며 새 생성 경로의 출력 계약이 아니다.

[Product 입력 재구성 초안](../specs/drafts/product-comparison-model-context.md)은 대체된 제안으로
보존한다. 고유 근거를 새 입력에 전달하는 원칙은 도구 내부에서 적용하되, 초안의 Product
middleware·snapshot 검증·제출 교정 순환은 구현하지 않는다.

## 결과와 재검토 기준

Product의 도구 선택 이력과 비교 작성 입력이 분리되고 비교 답변 생성 책임이 한곳으로
모인다. 답변 검증이나 재작성 순환이 제거되므로 출력 의미 오류는 그대로 나타날 수 있다.
이 결정은 답변 정확성 향상이나 입력 토큰 감소를 보증하지 않는다. 이전 시도와 검색 원문이
적은 실행에서는 입력량 감소도 작을 수 있다.

실제 평가에서는 상품·항목 식별, 원문과 문장의 의미 대응, 모·자펀드와 클래스·예외 보존,
선택 근거, 완료율·시간·provider 사용량을 따로 확인한다. 검증기 도입은 답변 형태와 오류
유형을 평가한 뒤 별도 결정으로 다룬다. 보완 검색이나 입력 예산을 도입할 때도 실패·호출·
시간 제한을 함께 정의한다.

## 관련 자료

- [Product 상품 비교 도구 스펙](../specs/components/product-comparison.md)
- [Product Agent 스펙](../specs/agents/product-agent.md)
- [전체 생성 모델 통일 결정](20260905-all-generation-hcx-007.md)
