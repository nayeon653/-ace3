---
status: accepted
date: 2026-09-06
type: architecture
related: []
supersedes:
  - 20260905-product-comparison-execution-budget.md
  - 20260906-product-comparison-minimal-criteria.md
  - 20260906-product-comparison-answer-ownership.md
  - 20260906-product-catalog-selection-retry.md
superseded-by: []
---

# 자유 비교 쿼리로 상품별 검색과 답안 작성을 연결한다

## 결정

고정 비교 항목과 셀 계약을 제거하고 Product가 사용자의 목적을 자유 문장으로 전달한다.

- `lookup_product_codes`는 상품 식별만 맡고 비교 항목을 입력받지 않는다.
- `compare_products(product_codes, comparison_query)`에서 Product가 비교 쿼리를 작성한다.
  Python은 앞뒤 공백만 정리한 같은 쿼리로 상품마다 한 번 검색하며 문서 범위만 달리한다.
- 독립 HCX에 원문 질문·판단 목표·비교 쿼리·전체 대상·상품별 검색 근거를 전달한다.
  생성한 답변과 선택 근거를 반환하고 Product와 Main은 비교 답안을 재작성하지 않는다.
- 항목 enum·1~3개 상한, 셀·coverage·셀 검증과 미사용 보완 검색 구현을 제거한다.
  식별·근거 부족 안내는 Python의 간단한 `comparison_answer`로 통일한다.
- 이름·코드 의미 검사를 두지 않는 정책과 실행 불가 선택의 Product 재조회 1회는 유지한다.
  답변 의미 검증과 내용 교정 호출은 추가하지 않는다.

## 이전 결정과의 관계

최소 항목 결정을 대체한다. 실행 예산·답변 소유권·카탈로그 재조회 기록에서는 고정 항목,
셀 결과·미완료 안내와 관련된 부분만 대체한다. 독립 생성 책임, 상품 최대 5개, 기존
검색·생성 deadline·모델 설정과 실행 불가 선택의 재조회 예산은 유지한다.
기존 채택 기록의 본문과 완료된 실험은 당시 내용으로 보존한다. 이전 항목·셀 방식의
실험 결과는 새 비교 쿼리의 검색 적합성이나 답안 품질을 입증하지 않는다.

상세 계약은 [비교 도구 스펙](../specs/components/product-comparison.md), 구현과 검증은
[PR #167](https://github.com/nayeon653/-ace3/pull/167)에 연결한다.
