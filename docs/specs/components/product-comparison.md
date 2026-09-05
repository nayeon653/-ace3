# Product 상품 비교 도구 스펙

- 상태: 구현 계약
- 작성일: 2026-09-05
- 구현: `pension_agent/agent/product/comparison.py`, `comparison_submission.py`
- 설정: `pension_agent/config/product_comparison.py`

상위 계약은 [Product Agent](../agents/product-agent.md),
[Catalog Planner](../agents/product-catalog-query-planner.md),
[Search Service](search-service.md)를 따른다. 구조·귀속·실행 예산의 검증과 실제 HCX가 작성한
비교 내용의 품질 평가는 구분한다. 이 문서는 특정 실행의 비교 성공이나 최대 크기 입력의
생성 품질을 보증하는 평가 기록이 아니다.

## 1. 해결할 문제와 책임

기존 Catalog Planner는 조회 계획 하나만 반환하고, 특정 상품 식별은 코드 하나만 허용했다.
명시적인 복수 비교를 여러 Tool 호출로 표현하면 검증에 실패해 문서를 검색하지 못했다.
비교 대상을 단일 계획 안의 배열로 표현하고, 코드 존재에 더해 질문 표현과 상품의 대응을
검증한다.

`compare_products`는 검증된 복수 상품에 같은 비교 항목을 적용해 상품별 원문 근거와 검색
상태를 반환하는 native async Tool이다. Product Agent에만 노출한다.

| 주체 | 책임 |
|---|---|
| Main Supervisor | 상품 비교 판단을 `analyze_product`에 위임하고 검증된 결과·제한을 보존 |
| Catalog Planner + Python | 원문의 비교 대상을 분리하고 상품명·코드 대응을 검증 |
| `compare_products` | 상품별 문서 범위 검색, 실행 예산·근거·부분 실패 관리 |
| Product HCX | 항목별 근거 해석, 비교 가능성 판단, 조건별 설명과 최종 제출 |
| Python 제출·응답 조립 | 대상·셀·근거 참조 검증 및 비교 결과의 최종 응답 보존 |

도구 내부에는 새 생성 LLM 호출을 추가하지 않는다. 기존 Search Service와 임베딩을 사용한다.
생성 역할은 모두 HCX-007, Thinking `none`을 유지한다. 자동 상품 선정·전체 카탈로그 순위화,
개인 포트폴리오 최적화는 범위에 포함하지 않는다.

## 2. 선행 계약: 복수 대상 식별

각 모델 응답에서 `return_product_catalog_query`를 정확히 한 번 호출하는 규칙은 유지한다.
Query union의 `resolve_products` route 안에 대상 배열을 담는다.
기존 단일 상품·전체/운용사 목록 route는 유지한다.

Product는 비교 요청의 `lookup_product_codes` 호출에 선택적 입력 `comparison_criteria`를
지정한다. Python이 3절의 enum·개수·중복을 검증한 뒤 Planner를 호출하고, 복수 식별 성공 시
대상과 항목을 state에 저장한다. 복수 route에는 이 입력이 필수이며, 단일 상품·목록 조회는
기존 무인자 호출을 유지한다. 따라서
0~1개 식별로 비교를 실행하지 않아도 요청 항목을 보존한다. 별도 비교 생성 모델은 추가하지
않으며, 카탈로그 코드 오선택에는 아래의 제한된 Planner 교정만 허용한다.

```text
ResolveProductsQuery {
  route: "resolve_products",
  targets: [
    {
      mention_parts: string[],
      resolution_status: "single" | "ambiguous" | "not_found",
      product_code?: string
    }
  ]
}
```

- `mention_parts`는 질문에서 그대로 가져온 상품 식별 표현이다. 공통 이름과 수식어가 떨어져
  있으면 여러 조각으로 보존한다. 예: `["솔로몬", "국공채", "단기"]`.
- Python은 배열 순서대로 `target_1`부터 실행 내 `target_id`를 부여하고 원문·식별 결과를
  state에 보존한다.
  `single`만 코드가 필수이고 나머지는 코드 필드가 금지된다. 공식명·운용사는 카탈로그가 채운다.
- 전체 `targets`는 미식별·동일 코드의 반복 표현까지 포함해 최대 5개다. 이를 초과하면 검색
  전에 상한 오류로 종료하고 일부를 버리지 않는다. 따라서 최종 셀도 최대 5×5개다.
- 명시적 복수 대상 요청에만 새 route를 사용한다. 하나의 모호한 이름을 임의의 비교 목록으로
  확장하거나 전체 카탈로그 추천 요청을 특정 상품 비교로 바꾸지 않는다.
- 정규화는 공백·문장부호·대소문자와 버전 관리되는 alias를 사용한다. 원문에 있는 시리즈명,
  기간, 호수 등 구별 표현이 선택된 공식명/alias와 대응해야 한다. 공통 단어만으로 확정하지
  않는다. 기간 등 구별 표현의 부분 문자열 일치만으로 서로 다른 수식어를 동일시하지 않는다.
  정확한 코드 입력은 카탈로그와 직접 대조한다.
- 코드 존재·운용사 일치에 더해 원문 표현의 후보 집합과 선택 코드가 일치해야 한다. 후보가
  하나로 확정되지 않으면 `single`을 거절한다. 모델이 제출한 `ambiguous` 또는 `not_found`는
  미식별 상태로 보존한다. 코드 오류를 다른 상품으로
  대체하지 않는다. 형식 오류는 `failed`, 유효하지만 미식별인 대상은 조건 부족으로 구분한다.
- 이름만 있는 입력의 모든 대상을 추출했는지는 모델의 의미 판단이 포함된다. Python의
  원문 조각·후보 검사만으로 누락 없는 의미 해석까지 보장한다고 주장하지 않는다.

원문 조각이 모두 유효하고 `single` 대상의 후보가 각각 정확히 하나인데 제출 코드만 다른
경우에는 같은 HCX Planner에 오류 대상·선택 코드·카탈로그 후보 metadata를 전달해 한 번만
전체 계획을 재제출시킨다. 응답당 Tool 한 개, 원래 대상 수·순서·원문 조각·식별 상태를 유지하고
전체 결과를 재검증한다. Python이 코드를 자동 치환하지 않는다. 형식 오류, 원문에 없는 조각,
후보 모호함에는 이 교정을 적용하지 않으며 다시 실패하면 종료한다. 초기 호출과 교정은 같은
Domain deadline 및 HCX 동시성 제한을 공유한다.

확정된 서로 다른 상품이 2개 이상일 때만 비교 Tool을 호출한다. 미식별 대상은 제거하지 않고
원래 요청의 제한으로 함께 보존한다. 0~1개이면 비교 Tool을 호출하지 않고 Python이 모든
요청 셀을 `not_verified`, coverage를 `none`, 판단을 `undetermined`로 생성한다. 개별 상품
사실을 추가 검색해 비교 완료로 표시하지 않는다. 동일 코드의 반복 표현은 target 연결을
유지한 채 하나의 검색 대상으로 묶는다.

## 3. Tool 입력

```json
{
  "product_codes": ["KR5153420063", "KR5153420079", "KR5153420105"],
  "criteria": ["investment_strategy", "risk", "capital_protection"]
}
```

| 필드 | 타입·검증 |
|---|---|
| `product_codes` | 중복 없는 코드 배열, 2~5개, state의 확정 코드 전체와 순서까지 일치 |
| `criteria` | 중복 없는 아래 enum 배열, 1~5개, state의 `comparison_criteria`와 순서까지 일치 |
| ToolRuntime | 질문 원문, 전체 targets, catalog version, 상위 deadline과 실행 상태 자동 주입 |

| criterion | 비교 범위 |
|---|---|
| `investment_strategy` | 투자 대상·비중, 만기·듀레이션, 비교지수와 운용 방식 |
| `risk` | 공시 위험등급·위험지표·금리 등 가격변동 위험 |
| `capital_protection` | 원금보장 여부, 원금손실 가능성, 예금자보호 |
| `fees` | 보수·비용·판매/환매수수료의 종류, 클래스와 적용 조건 |
| `liquidity` | 환매 절차·지급 시점·제한, 보유기간 관련 조건 |

`안정성` 요청은 프롬프트에서 최소한 `risk`와 `capital_protection`을 선택하도록 지시한다.
이는 Python 키워드 라우팅이 아니므로 매핑 품질은 평가로 검증하며, 모든 질문에 비용·유동성을
자동 추가하지 않는다. 검색 표현은 `prompts/domain/product-comparison-search.json`에서
버전 관리한다.

모델은 파일명·문서 ID·검색 개수·정렬·timeout을 입력하지 않는다. 추가 필드는 금지한다.
미등록 코드, 확정 대상의 임의 추가·누락, 중복 코드, 개수 초과, 잘못된 criterion은 검색 전에
거절한다. 개수가 많다는 이유로 앞의 일부만 자동 선택하지 않는다.

## 4. Tool 출력과 상태

```text
ComparisonEvidenceResult {
  execution_status: "completed" | "failed" | "timeout",
  catalog_version: string,
  criteria: ComparisonCriterion[],
  targets: ResolvedOrUnresolvedTarget[],
  products: ProductEvidence[],
  retrieval_coverage: "all_products" | "some_products" | "no_products",
  limitations: string[],
  error?: string
}
ProductEvidence {
  product_code: string,
  official_name: string,
  provider: string,
  source_file_name: string,
  attempts: SearchResult[],
  evidence: SearchChunkPayload[]
}
```

`targets`는 2절의 모든 대상, `target_id`, 상태 및 확정된 경우의 코드를 포함한다.
`products`는 확정 코드마다 정확히 한 항목이며 입력 순서를 유지한다. `source_file_name`은
카탈로그의 문서 alias를 Python이 해석한다. 정식 상품명이 동일 문서에 등장한다는 이유로
다른 상품의 수치나 클래스를 공유하지 않는다.

`attempts`는 각 검색 시도의 기존 [SearchResult](../../../pension_agent/agent/search/schemas.py)를
보존한다. 실패·시간 초과 시도의 청크는 비어 있어야 한다. `evidence`는 해당 상품에서 완료된
시도의 청크를 ID로 중복 제거한 누적 결과다. 후속 실패가 앞선 성공 근거를 삭제하지 않는다.
검색을 시작하지 못한 상품도 빈 `products` 누락 대신 정제된 실패/timeout 시도를 남긴다.

위 구조는 Search Service 결과를 보존하는 **내부 service 반환·state 계약**이다. Product 모델에
보내는 ToolMessage는 별도 표현을 사용한다. `products[].attempts[].retrieved_chunks`만
제외하고, 같은 원문은 상품별 `products[].evidence`에 ID로 중복 제거한 형태로 한 번 유지한다.
각 시도의 실행 상태·오류·제한은 메시지에도 남으며 state의 전체 `SearchResult`는 수정하지
않는다. 문서 alias를 공유하는 상품 사이의 근거 귀속도 유지한다.

ToolMessage에는 비교 셀 제출을 안내하는 `next_step` 문자열을 덧붙인다. 이 필드는
모델 메시지 전용이며 `ComparisonEvidenceResult`, 최종 `DomainResult` 또는 외부 API의
필드가 아니다. 서비스 반환값을 다시 검증할 때 압축한 메시지를 입력으로 사용하지 않는다.

`retrieval_coverage`는 **확정된 검색 대상** 중 청크가 하나 이상 있는 상품 수로만 계산한다.
모든 요청 대상이 식별됐거나 모든 비교 항목이 입증됐다는 의미가 아니다. 미식별 대상은
`targets`에 남으므로 `all_products`여도 최종 비교는 부분 결과일 수 있다.

| 수집 결과 | Tool 상태 | 최종 Domain 판단의 범위 |
|---|---|---|
| 성공 시도가 있고 모든 확정 상품에서 청크 확보 | `completed / all_products` | 셀별 의미 검토 후 판단 |
| 성공 시도가 있고 일부 상품에서만 청크 확보 | `completed / some_products` | 부분 설명, `conditional` 또는 `undetermined` |
| 성공 시도가 있으나 청크 0개; 다른 실패가 섞여도 동일 | `completed / no_products` | `undetermined`, 검색 실패도 제한에 보존 |
| 성공 시도 없이 모두 timeout | `timeout / no_products` | Domain timeout, 근거 없음 |
| 성공 시도 없이 failed가 하나 이상; timeout 혼합 포함 | `failed / no_products` | Domain failed, 근거 없음 |
| 입력 계약 위반 | 검색 전 `failed / no_products` | 정제된 오류, 입력을 바꾼 우회 금지 |

Tool 전체가 `failed/timeout`이면 누적 근거가 없어야 하고 `error`가 필수다. `completed`에는
`error`를 넣지 않고 상품별 오류를 `attempts`와 `limitations`로 전달한다. 입력 검증 실패의
`products`는 빈 배열로 두며, 위의 항목 수·순서 규칙은 검증을 통과한 실행에 적용한다.

## 5. 실행 순서와 예산

```text
lookup_product_codes → resolve_products 검증
  → compare_products → 상품별 SearchService.search 병렬 실행
  → 필요하고 예산이 남으면 상품별 search_documents 보완
  → Product HCX의 비교 셀 해석 → submit_domain_result
  → 비교 구조 검증 → DomainResult → Main → API 응답 보존
```

최초 검색은 공식 상품명과 선택된 criteria의 검색 표현을 이어 붙인 질의를 각 대상에 한 번씩
배정한다. 문서 범위는
상품별로 제한하며 `Permission.PRODUCT`를 적용한다. 최초 batch가 완료되거나 검색 마감에
도달한 뒤 누락 항목만 기존 `search_documents`로 보완할 수 있다. batch를 다시 실행하지 않는다.

`comparison_targets`가 있는 모델 호출에만 비교 전용 Tool availability middleware를 적용한다.
현재 단계에 실행할 수 있는 Tool schema와 과거 Tool 메시지를 HCX가 해석하는 데 필요한
schema를 함께 남긴다. 최초 비교 검색 전에는 `tool_choice=compare_products`를 지정한다.
검색 후에는 Tool 선택 지정을 생략해(`tool_choice=None`, 기본 auto) 보완 검색을 선택할 수
있게 한다. 가장 최근 AIMessage의 Tool 호출이 비어 있어 재지시했거나 보완 검색 상한을
소진해 제출만 허용되면 `tool_choice=submit_domain_result`로 제출 Tool을 지정한다.
빈 호출에는 자유 문장과 순서 검사에서 불허 호출을 제거한 경우가 포함된다. 과거 Tool의
schema를 남겼다고 재실행이 허용되지는 않으며 기존 순서·횟수 검사가 이를 거절한다.
단일 상품·카탈로그 조회 경로의 모델 Tool 선택 설정은 변경하지 않는다.

아래 값은 전용 불변 config와 역할별 모델 config에서 관리한다.

| 항목 | 기본값 |
|---|---|
| 전체 target / criteria / 셀 상한 | 5 / 5 / 25, 미식별·반복 target도 포함 |
| `lookup_product_codes` / `compare_products` | 요청당 각각 1회 |
| Catalog Planner 모델 호출 | 기본 1회, 유일 후보와 코드 불일치 교정에만 최대 1회 추가 |
| 최초 Search Service 호출 | 확정 상품 N개에 대해 N회 |
| 보완 Search Service 호출 | 요청 전체 최대 2회, 같은 상품에는 최대 1회 |
| 전체 검색 횟수 | N + min(N, 2) 이하, 실패 시도도 차감 |
| 비교 검색 시간 / 최종 Product 제출 여유 | 최대 30초 / 최소 30초 예약 |
| Product 모델 호출 수 | 기존 최대 5회 유지, 보완·제출 수정도 포함 |
| Product 최대 출력 토큰 | 4096, Main·Planner는 1024 유지 |
| 동시성 / 상위 deadline | 기존 프로세스 제한, Domain 75초·API 180초 유지 |

비교 진입 시 검색 마감은 `min(현재 시각 + 30초, Domain deadline - 30초)`로 한 번 정한다.
최초·보완 검색의 대기·embedding·Qdrant·재시도 모두 이 마감을 공유하고 연장하지 않는다.
남은 시간이 없으면 검색을 새로 시작하지 않고 현재 확보 범위로 제출한다. 검색 단계에 남은
task는 취소·회수하며 기존 동시성 제한을 우회하는 별도 무제한 pool을 만들지 않는다.

30초 예약은 제출 성공 보장이 아니다. 부모 deadline 또는 외부 취소가 먼저 발생하면 이를
전파한다. 현재 GuardedDomainRunner는 부모 timeout 시 근거 없는 timeout을 반환하므로,
**부분 근거 보존은 부모 마감 전 정상적으로 결과를 제출했을 때만** 보장한다.
현행 `max_search_calls=2`에 N회 batch를 1회로 숨기지 않고 실제 검색 예산을 별도로 집계한다.
최초 시도 이후 `attempts` 개수로 보완 검색을 차감한다. 미등록 대상·횟수 상한·지난 마감으로
새 보완 검색을 거절한 경우에는 기존 결과를 유지하고 제한만 추가한다. `search_deadline`은
결과 객체의 내부 필드이며 Tool 메시지의 JSON에서 제외한다. 후속 검색을 위해 state에는
직렬화한 사본 대신 결과 객체를 보관한다.

Product 출력 상한의 근거와 재검토 조건은
[출력 예산 결정](../../decisions/20260905-product-comparison-execution-budget.md)을 따른다.

## 6. 비교 셀과 근거의 의미

Product HCX는 모든 요청 대상 × 요청 criteria의 셀을 제출한다. 한 셀의 형태는 다음과 같다.

```text
ComparisonCell {
  target_id: string,
  criterion: ComparisonCriterion,
  status: "supported" | "not_verified" | "conflicting" | "not_comparable",
  finding: string,
  evidence_refs: [{product_code: string, chunk_id: string}],
  limitations: string[]
}
```

- `supported`에는 해당 상품의 원문 근거가 필요하다. 원문에 공시된 정적 값은 단위·클래스·
  기준일·상한 여부를 보존한다. 검색 청크가 있다는 이유만으로 이 상태를 부여하지 않는다.
- `not_verified`에는 미식별, 검색 실패, 필요한 사실 미발견 등 이유를 남긴다. 빈 결과를
  “그 위험이 없음”, “수수료 0원”처럼 해석하지 않으며 `evidence_refs`는 빈 배열이다.
- `conflicting`은 충돌하는 원문을 최소 2개 참조하며 하나를 임의로 최신 값으로 선택하지 않는다.
- `not_comparable`은 각 상품에서 사실은 확인돼도 지표·단위·클래스·기준시점 차이 때문에
  직접 우열을 판단하기 어려운 경우다. 해당 상품의 사실 근거를 최소 1개 참조하고 확인된
  사실과 비교 제한을 함께 보존한다. 기준시점을 확인할 근거 자체가 없으면 `not_verified`다.

현재 SearchChunkPayload에는 공시일 전용 metadata가 없다. 원문에서 날짜를 확인했으면 해당
chunk를 인용하고, 확인하지 못하면 미확인으로 남긴다. 카탈로그 버전·검색 순위·문서 내 날짜
하나를 근거로 최신 공시라고 보장하지 않는다. 과거 변경 이력과 현행 본문을 구분한다.

근거 귀속은 `(target_id, product_code, source_file_name, chunk_id)` 관계로 검증한다. 문서
alias 때문에 동일 청크가 여러 상품 검색에서 나올 수 있어 chunk 하나를 무조건 상품 하나에
역매핑하지 않는다. 해당 본문이 실제 상품·클래스를 설명하는지는 HCX가 확인하고 평가한다.

도구는 수익률 차이·비용·위험값을 새로 계산하지 않는다. 계산 요구가 섞이면
[공통 계산 계약](../../../PROJECT_RULES.md)을 따른다. 기존 단일 상품용 Calculation Tool을
복수 후보 state에 그대로 적용하지 않으며, 다상품 계산 컨텍스트 확장은 현재 범위 밖이다.
계산을 수행하지 못한 요구는 누락 조건으로 남기고 공통 규칙 밖의 LLM 계산으로 채우지 않는다.

## 7. 제출과 Main·API 연결

내부 `DomainResult`와 Main용 `DomainToolResult`는 선택적 `comparison_result`를 포함한다.
기존 단일 상품·카탈로그 결과에는 이 필드를 넣지 않는다. 외부 `/answer`의 5개 필드는 유지한다.

```text
ComparisonResult {
  catalog_version: string,
  targets: ResolvedOrUnresolvedTarget[],
  criteria: ComparisonCriterion[],
  coverage: "complete" | "partial" | "none",
  cells: ComparisonCell[],
  limitations: string[]
}
```

Product는 `submit_domain_result.comparison_cells`로 셀을 제출한다. Python이 이를 검증하고
state의 targets·criteria·catalog version을 결합한다.
비교 state에서 모델에 노출하는 제출 schema는 `comparison_cells`를 null 없는 필수 배열로
제한하고 길이를 전체 대상 수 × 항목 수로 고정한다. `evidence_chunk_ids`는 빈 배열만
허용하고, 결론은 표를 반복하지 않는 짧은 조건별 요약으로 지시한다. 실행 Tool의 공통
schema를 변경하지 않고 모델 바인딩의 사본에만 적용하므로 단일 상품 제출 계약은 유지한다.
모델이 대상 목록을 바꿔 제출하지 못하게 한다. 최종 evidence는 셀에서 실제 인용한 청크의
합집합이며, 단순 검색 결과 전체를 넣지 않는다. 0~1개 식별로 비교를 실행하지 못했을 때도
미확인 셀과 요청 대상들을 이 구조에 보존할 수 있다.

제출 검증 조건:

1. `comparison_result`는 `domain=product`, `execution_status=completed`에서만 허용하고
   `catalog_result`와 함께 넣지 않는다. 기존 실패 Domain에는 근거·비교 결과를 넣지 않는다.
2. 모든 `(target_id, criterion)` 조합이 정확히 한 번 존재하고 대상·항목을 추가하지 않는다.
   미식별 대상 또는 누적 근거가 없는 상품은 `supported`로 제출할 수 없다.
3. 모든 ref가 해당 상품의 완료된 검색 결과에 존재하고 최종 `evidence`에도 포함돼야 한다.
   미확인 셀은 확인된 비교 사실을 생성하지 않는다. 인용이 필요한 셀에 빈 ref는 금지한다.
4. `complete`는 모든 대상이 식별되고 모든 셀이 `supported`인 경우다. 그 외에 유효 ref를 가진
   `supported/conflicting/not_comparable` 셀이 하나라도 있으면 `partial`, 없으면 `none`이다.
   따라서 모든 셀이 근거 있는 `not_comparable`인 경우도 `partial`이다. coverage는 제출된
   유효 셀로 Python이 계산하며, 의미적 사실 검증까지 완료됐다는 뜻은 아니다.
5. `partial/none`은 각각 `conditional/undetermined`와 구체적인 누락 조건으로 제출한다.
   `complete`여도 사용자 조건이 부족하면 `conditional`이다. 모든 위험등급이 같다는 이유로
   개인 적합성까지 `determined`로 올리지 않는다.

Main에 평문 결론만 전달하면 상품별 근거 대응이 사라지므로 비교 구조도 함께 전달한다.
Main은 새 비교 사실·우열·추천을 추가하지 않는다. 응답 조립은 Product의
`decision.conclusion`에 담긴 조건별 설명, 비교 표, `missing_conditions`, `warnings`와 비교
제한을 모두 보존한다. conclusion의 사실·조건별 결론은 셀 근거와 질문의 조건에 한정한다.
`coverage=none`이면 conclusion의 자유 생성 내용을 채택하지 않고 미식별·검색·근거 부족
상태로부터 판단 불가 안내를 구성한다.

비교 결과가 있으면 `comparison_formatting.py`가 모든 대상×항목을 행으로 가진 표, 셀 상태,
출처 번호, 확인 조건과 경고를 결정론적으로 직렬화하고 Main의 추가 문장은 채택하지 않는다.
`not_verified` 셀의 자유 형식 finding은 표시하지 않고 미확인 안내와 제한을 출력한다.
복합 Domain 요청은 다른 Domain 결과도 각각 보존하고 자유 문장으로 재계산하거나
새 적합성 판단을 합성하지 않는다. 모든 관련 Domain이 실패하고 근거도 없으면 정제된
실패 안내만 반환하며 Main의 무근거 일반론을 채택하지 않는다.

이는 구조·귀속·누락 검사다. finding이 인용 원문의 의미를 정확히 표현하는지까지 Python이
증명하는 것은 아니며, 해당 품질은 HCX 프롬프트와 근거 일치 평가로 검증한다.

## 8. 추적과 회귀 검증

LangSmith 사용 범위는 [기존 개인 추적 정책](../../operations/langsmith-tracing.md)을 따른다.
새 root를 만들지 않고 `main_supervisor → analyze_product → product_agent → compare_products
→ search_service` 아래에 연결한다. 요청 대상·식별 결과, 상품별 검색 상태·호출 수·시간,
retrieval coverage, 최종 셀 coverage와 사용 근거를 구분해 확인한다.
HTTP 200과 trace의 `error=null`만으로 비교 성공을 집계하지 않는다.

| 검증 사례 | 통과 조건 |
|---|---|
| 국공채 단기·중장기·장기 3종 비교 | 계획 1개·정확한 3코드·상품별 근거·전체 요청 셀 보존 |
| 다른 등록 상품 코드 선택 | 코드 존재만으로 통과하지 않고 원문 대응 검사에서 거절 |
| 모호한 단일 상품명 | 비교 요청으로 확대하지 않고 후보 모호함 보존 |
| 3대상 중 2개 / 1개 / 0개 식별 | 각각 부분 비교 / 비교 미실행 / 비교 미실행, 대상 누락 없음 |
| 중복·미등록·대상 추가/누락·6개 이상 | 검색 전 거절, 자동 부분 선택 금지 |
| 성공+실패, 빈 성공+실패, 모두 timeout/혼합 실패 | 4절 상태표와 일치 |
| 보완 검색 실패 | 기존 성공 근거 유지, 해당 상품 오류도 보존 |
| 공유 문서 alias·상이한 클래스·기준일·변경 이력 | 타상품 사실 전용·최신성 단정·잘못된 직접 비교 금지 |
| 검색 마감 / 부모 취소 | 남은 task 회수, 예약 시간·상위 deadline 준수, 취소 전파 |
| 최대 5상품×5항목 | JSON 잘림·셀 누락 없음, 생성 토큰·총지연·동시성 예산 확인 |
| 일부 근거 또는 전부 근거 없음 | 제한 보존, 빈칸 추정·새 상품 추천 금지 |
| 최종 Main/API | 구조화 비교와 실제 인용 근거 보존, API 필드는 정확히 5개 |

상품 코드 회귀 fixture는 카탈로그의 솔로몬 단기 `KR5153420063`, 중장기 `KR5153420079`,
장기 `KR5153420105`를 사용한다. 오선택 fixture `KR5153420022`는 라이프사이클7090연금이다.
상품별 등급·수치·최신성은 테스트 입력 문서에서 주입하고 제품 코드에 고정하지 않는다.
개인 질문 원문, LangSmith 링크·workspace ID, 인증값은 공용 평가 문서에 기록하지 않는다.

## 9. 구현 경계와 검증 위치

| 구현 경계 | 책임 |
|---|---|
| Catalog Planner·프롬프트 | 복수 route·원문 대응 검증·미식별 대상 보존 |
| Product Tool·state·middleware | 비교 Tool 등록, 상품별 attempts/근거, batch·보완 예산과 순서 |
| 공통 Domain 계약·Domain Tool adapter | optional comparison_result 검증·Main 전달 |
| Product 제출·AnswerService·API presentation | 셀 근거 검사·부분 결과·결정론적 비교 표시·무근거 생성 차단 |
| config·현재 스펙·결정 기록·회귀 평가 | 토큰/시간/호출 설정, 구현과 문서의 동시 갱신 |

- `tests/unit/agent/test_product_catalog_query.py`: 복수 계획·원문 조각·코드 대응
- `tests/unit/agent/test_product_comparison.py`: 상품별 검색·상태·예산·취소·문서 범위
- `tests/unit/agent/test_comparison_contracts.py`: 대상×항목 셀·최종 근거·응답 보존
- `tests/unit/agent/test_domain_agents.py`: Product 실행 경로와 기존 Tool 호환

HCX 실호출에서는 상품 표현의 누락, 인용 의미, 25셀 출력의 잘림과 누락, 전체 지연을 별도로
평가한다. 계약 테스트의 통과를 실제 문서 비교 품질의 통과로 집계하지 않는다.
