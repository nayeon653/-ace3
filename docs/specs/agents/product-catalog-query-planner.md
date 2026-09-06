# Product Catalog Query Planner 스펙

## 지위와 목적

Product Catalog Query Planner는 독립 Domain Agent가 아니다. Product Agent의
`lookup_product_codes` Tool 내부에서 전체 상품 카탈로그와 사용자 표현을 대조해 Python이
실행할 조회 계획 하나를 만드는 제한된 LLM 컴포넌트다.

상품 문서를 검색하거나 상품 특성·우수성·적합성을 판단하지 않는다.

## 모델과 입력

| 항목 | 값 |
|---|---|
| 모델 | `HCX-007` |
| Thinking | `none` |
| temperature / 최대 토큰 | `0.1` / `1024` |
| Provider timeout/retry | 호출당 30초, 최대 2회 retry |
| 프롬프트 | `pension_agent/prompts/domain/product-catalog-query-planner.md` |
| 구현 | `pension_agent/agent/product/catalog_query.py` |

시스템 프롬프트에는 검증된 전체 `product_catalog.json` 스냅샷을 정확히 한 번 삽입한다.
사용자 메시지는 다음 JSON이다.

```json
{"question":"사용자 질문 원문","objective":"Product Agent의 판단 목표","retry_hint":"재조회 시 전달하는 선택적 설명"}
```

`retry_hint`는 Product가 실행 불가 선택 오류를 받은 뒤 재조회할 때만 추가하는 선택적
문자열이다. 질문과 판단 목표는 바꾸지 않는다. 이 입력들은 해석할 데이터이며 그 안의
지시를 시스템 명령으로 취급하지 않는다.

## 출력 계약

모델은 자유 형식 텍스트 대신 각 응답에서 `return_product_catalog_query` Tool을 정확히
한 번 호출한다.
Tool 인자는 `{"query": {...}}` 형태이며 route별 추가 필드를 금지한다.

| route | 의미 | 핵심 필드 |
|---|---|---|
| `resolve_product` | 단일 상품 확정 | `resolution_status=single`, `product_code`, 선택적 `provider` |
| `resolve_products` | 명시적인 2~5개 비교 대상 | `targets[]`의 `mention_parts`, `resolution_status`, 확정된 경우만 `product_code` |
| `product_not_found` | 상품 미등록 | `resolution_status=not_found`, 선택적 `provider` |
| `product_ambiguous` | 둘 이상 후보 | `resolution_status=ambiguous`, 선택적 `provider` |
| `browse_all_catalog` | 전체 개수·목록 | `return_mode` |
| `browse_provider_catalog` | 공식 운용사별 개수·목록 | `provider`, `return_mode` |
| `provider_not_found` | 운용사 미등록 | 입력의 `provider`, `return_mode` |

`return_mode`는 `count`, `items`, `count_and_items` 중 하나다.

복수 비교의 `mention_parts`는 질문 원문에 실제 나타나는 상품명 조각이다. 공통 시리즈명과
수식어가 떨어져 있으면 조각 배열로 보존한다. 상품 코드는 공식명 대신 카탈로그의 정규화된
코드 문자열을 사용한다. 미확정 대상에는 코드 필드를 넣지 않는다.

## 식별 규칙

1. 질문의 정확한 상품 코드를 우선 대조한다.
2. 코드가 없으면 고유 상품명 표현을 모든 공식명과 alias에 대조한다.
3. 연금, 펀드, 주식, 채권, 위험, 비용처럼 공통 단어만으로 상품을 식별하지 않는다.
4. 단일 대상의 후보 하나일 때만 `resolve_product`를 사용한다.
5. 단일 대상의 후보가 둘 이상이면 `product_ambiguous`, 없으면 `product_not_found`를 사용한다.
6. 등록되지 않은 운용사를 유사한 공식 운용사나 전체 조회로 대체하지 않는다.
7. 카탈로그 순서상의 임의 상품 코드를 스키마 채움용으로 선택하지 않는다.
8. 명시적인 복수 대상만 `resolve_products`에 담는다. 모호한 이름 하나를 비교 목록으로
   확장하지 않으며, 미등록·모호한 대상도 배열에서 제거하지 않는다.

## Python 실행 확인

모델의 Tool 호출은 Pydantic discriminator union으로 읽고, 같은 카탈로그 스냅샷에서
조회가 가능한지 확인한다.

- 응답당 Tool 한 개, route별 필드 조합과 자료형
- 복수 대상 2~5개, 비어 있지 않은 `mention_parts`, 확정 대상의 코드 필수·미확정 대상의 코드 금지
- 상품 코드의 실제 존재와 선택적 공식 운용사 일치
- 운용사 등록 여부·공식명 정규화, 카탈로그 조회의 정확한 개수와 목록

상품명의 오타·약칭·기간·호수 해석과 카탈로그 항목 선택은 모델의 책임이다. Python은
`mention_parts`의 원문 등장 여부나 공식명·alias 대응, 후보의 유일성을 검사하지 않는다.
이름에 관한 고정 규칙과 Planner 내부의 코드 교정 호출은 사용하지 않는다. 카탈로그에 있는
다른 상품 코드를 잘못 선택한 경우도 실행 가능하므로 통과하며, 의미 정확성은 별도 평가한다.

## 실행 불가 선택의 Product 재조회

카탈로그가 처리할 수 없는 코드 문자열, 존재하지 않는 코드, 코드·운용사 불일치나 등록된
운용사를 미등록으로 표시한 계획은 실행 불가 선택으로 처리한다. 정제된 오류와
`submitted_query`를 `retryable=true`인 Tool 결과로 Product에 전달한다. 등록되지 않은
운용사의 조회 계획을 기존 `provider_not_found`로 정규화하는 동작은 유지한다.

Product가 재조회 여부와 `retry_hint`를 결정하며, Planner는 새 요청에서 계획 하나만 만든다.
카탈로그 조회는 상품 식별만 담당하며 비교 항목이나 `comparison_query`를 입력으로 받지 않는다.
Python이 대체 코드를 제시하거나 Planner가 내부에서 전체 계획을 다시 제출하지 않는다.
원문 질문과 판단 목표는 그대로 유지한다. 재조회는 최대 한 번이며 두 번째 조회도 실패하면
Product를 `failed`로 종료한다. 사용자에게 되묻는 절차가 아니라 같은 요청의 내부 도구 호출이다.

## 실행 제한과 실패

- 한 `lookup_product_codes` 호출에서 Planner 모델은 논리적으로 한 번 호출된다.
- 실행 불가 카탈로그 선택에 대한 Product 재조회만 허용하므로 전체 조회는 최대 2회다.
- 최초 조회와 재조회는 Product의 기존 모델 호출 상한·75초 deadline·HCX 동시성을 공유한다.
- Tool 호출 없음·복수 호출·다른 Tool 호출, 빈 필수값·잘못된 자료형·필드 누락은 응답 형식 오류다.
  provider 호출 오류와 응답 형식 오류는 `retryable=false`로 종료하고 Product 재조회를 하지 않는다.
- timeout은 기존 Product Domain의 `timeout`으로 분류한다. 상위 deadline·취소를 연장하지 않는다.
- 원시 모델 응답과 내부 예외는 API에 노출하지 않는다.

현재 선택·재조회 정책은
[카탈로그 선택·재조회 결정](../../decisions/20260906-product-catalog-selection-retry.md)을 따른다.

## 검증 위치

- `tests/unit/agent/test_product_catalog_query.py`
- `tests/unit/agent/test_domain_agents.py`
