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
{"question":"사용자 질문 원문","objective":"Product Agent의 판단 목표"}
```

`question`과 `objective`는 정규화 대상 데이터이며 그 안의 지시를 시스템 명령으로 취급하지
않는다.

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

## Python 재검증과 실행

모델의 Tool 호출은 Pydantic discriminator union으로 검증한다. 이후 Python이 같은 카탈로그
스냅샷으로 다음을 다시 확인한다.

- 상품 코드의 실제 존재와 공식 운용사 일치
- 운용사 등록 여부와 공식명 정규화
- route별 필드 조합
- 카탈로그 조회의 정확한 개수와 목록
- 복수 계획의 원문 조각 실제 등장 여부, 공식명 또는 같은 alias 내 모든 조각의 대응
- 기간·호수 경계를 구분한 후보 집합과 `single` 코드의 일치

복수 대상 검사는 `product_identity.py`가 소유한다. 공백·문장부호·대소문자 정규화와
카탈로그 alias를 사용하며, 국공채·연금·채권 같은 공통 용어만으로 상품을 확정하지 않는다.
`단기`와 `초단기`처럼 구별 수식어가 부분 문자열로 겹치는 경우도 서로 다른 대상으로
검사한다. 원문의 비교 대상을 빠짐없이 추출했는지와 미식별 상태 선택의 의미 정확성은
모델 판단과 별도 평가 범위다.

모델이 등록 운용사를 미등록으로 표시하거나 존재하지 않는 상품 코드를 만들면 결과를
신뢰하지 않고 정제된 Planner 실패로 처리한다. 등록되지 않은 운용사로 조회한 계획은
안전한 `provider_not_found`로 정규화할 수 있다.

### 복수 비교 코드의 제한된 교정

복수 계획이 형식 검증을 통과하고 모든 원문 조각이 질문에 있으며 각 `single` 대상의 후보가
정확히 하나인데 코드만 불일치한 경우, 같은 Planner 모델에 한 번만 교정을 요청한다.
피드백에는 오류 대상 번호, 원문 조각, 선택 코드와 해당 후보의 카탈로그 metadata를 넣는다.
모델은 전체 `resolve_products` 계획을 다시 제출하며, Python이 코드·후보 대응을 재검증하고
원래 대상 수·순서·원문 조각·식별 상태가 보존됐는지 확인한다. 자동 코드 치환은 하지 않는다.

원문에 없는 표현, 후보 모호함, 다른 route, 여러 Tool 호출, 잘못된 코드 형식에는 교정을
적용하지 않는다. 교정 자체가 실패하거나 원래 대상을 바꾸면 추가 재시도 없이 종료한다.

## 실행 제한과 실패

- 한 `lookup_product_codes` 호출에서 Planner 모델은 기본 한 번 호출된다. 위의 복수 비교
  코드 교정 조건에만 최대 한 번을 추가한다.
- Product Agent의 75초 deadline을 공유하며 이를 연장하지 않는다.
- 교정도 동일 deadline과 프로세스 HCX 동시성 제한을 사용한다.
- Tool 호출이 없거나 둘 이상이거나 다른 Tool을 호출하면 실패한다.
- timeout은 Product Domain의 `timeout`, 형식·검증 실패는 정제된 `failed` 결과로 변환된다.
- 원시 모델 응답과 내부 예외는 API에 노출하지 않는다.

## 검증 위치

- `tests/unit/agent/test_product_catalog_query.py`
- `tests/unit/agent/test_domain_agents.py`
