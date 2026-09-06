---
status: accepted
date: 2026-09-06
type: architecture
related:
  - 20260906-product-comparison-minimal-criteria.md
supersedes:
  - 20260905-product-comparison-execution-budget.md
  - 20260906-product-comparison-answer-ownership.md
superseded-by: []
---

# 상품 해석은 모델이 맡고 실행 불가 선택은 Product가 재조회한다

## 배경

이름의 고정 규칙은 오타·약칭을 충분히 해석하지 못한다. 상품 선택의 의미 판단과
카탈로그 조회를 실행할 수 있는지의 확인을 분리한다.

## 결정

- Planner는 호출마다 전체 카탈로그에서 조회 계획 하나를 만든다. Python은 자료형·기본
  계약·코드 존재·운용사 일치를 확인하며 이름·코드의 의미 대응과 후보 유일성을 검사하지 않는다.
- 코드 문자열을 처리할 수 없거나 없는 코드 등 실행 불가 선택은 이전 계획과 정제된 오류를
  Product에 돌려준다. Product가 `retry_hint`를 넣어 최대 한 번 재조회하며 총 조회는 2회다.
- 질문·판단 목표와 기존 Product 모델 호출 상한·deadline을 유지한다. 비교 항목 유지는
  프롬프트로 안내한다. Planner 내부 재제출이나 Python의 대체 코드 선택은 수행하지 않는다.
- provider 호출·응답 형식·비교 항목 오류는 재조회 대상이 아니다. 두 번째 조회 실패는 종료한다.
- 존재하는 다른 상품 코드의 의미 오선택은 통과할 수 있다. 이 정책은 식별 정확성을 보장하지
  않으며 오타·약칭·유사 상품 선택을 별도 평가한다. 비교 답변의 의미 검증은 추가하지 않는다.

## 이전 결정과의 관계

기존 [실행 예산](20260905-product-comparison-execution-budget.md)과
[답변 소유권](20260906-product-comparison-answer-ownership.md) 중 상품명·코드 검사, 내부 교정과
조회 횟수만 대체한다. 비교 생성 책임·항목 상한·검색 및 생성 예산은 기존 결정을 유지한다.
기존 기록의 본문과 완료된 실험 결과는 당시 내용으로 보존한다.

상세 계약은 [Catalog Planner](../specs/agents/product-catalog-query-planner.md)와
[Product Agent](../specs/agents/product-agent.md), 관련 구현은 [PR #167](https://github.com/nayeon653/-ace3/pull/167)에서 확인한다.
