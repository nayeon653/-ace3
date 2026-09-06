# Product 비교 작성 입력 재구성 초안

- 상태: 대체됨, 이 방식은 구현하지 않음
- 작성일: 2026-09-06

당시 제안은 Product의 답변 생성 책임을 유지하면서, 비교 작성 직전에 질문·대상·항목·
고유 근거·최신 검색 상태를 새 입력으로 구성하는 것이었다. 이전 도구 호출 이력과 중복
원문을 제외하되 전체 실행 이력은 state에 보존하고, 별도 요약용 LLM은 추가하지 않는 안이었다.

이후 [비교 답변 소유권 결정](../../decisions/20260906-product-comparison-answer-ownership.md)에서
검색과 비교 답변 작성을 `compare_products` 내부로 모으는 방향을 채택했다. 도구 내부의
독립 HCX가 답변을 완료하므로 Product의 작성 입력 middleware와 셀 제출 경로는 필요하지 않다.
답변 검증을 두지 않는다는 결정에 따라 초안의 snapshot 인용 검사와 오류 후 재제출 순환도
채택하지 않았다.

고유 근거와 현재 상태를 새 입력으로 전달한다는 원칙은 도구 내부 생성기에 적용했다.
현재 입출력·검색·생성·실패 계약은 [Product 상품 비교 도구 스펙](../components/product-comparison.md),
도구 선택과 실행 순서는 [Product Agent 스펙](../agents/product-agent.md)을 따른다.
