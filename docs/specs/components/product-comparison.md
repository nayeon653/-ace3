# Product 상품 비교 도구 스펙

- 상태: 구현 계약
- 작성일: 2026-09-05
- 갱신일: 2026-09-06
- 구현: `pension_agent/agent/product/comparison.py`, `comparison_answer.py`
- 설정: `pension_agent/config/product_comparison.py`, `pension_agent/config/hcx.py`

상위 계약은 [Product Agent](../agents/product-agent.md),
[Catalog Planner](../agents/product-catalog-query-planner.md),
[Search Service](search-service.md)를 따른다. 현재 생성 책임과 검증 범위는
[비교 답변 소유권 결정](../../decisions/20260906-product-comparison-answer-ownership.md)을 따른다.
이 문서는 실제 HCX 답변의 정확성이나 비교 품질을 보증하는 평가 기록이 아니다.

## 1. 해결할 문제와 책임

명시적인 복수 상품을 한 조회 계획의 배열로 식별한 뒤, `compare_products`가 상품별 문서
검색부터 비교 답변 작성까지 완료한다. Product의 앞선 도구 호출 이력과 비교 작성 입력을
분리하고, 완성된 답변을 Product가 다시 생성하지 않게 한다.

| 주체 | 책임 |
|---|---|
| Main Supervisor | 상품 비교 판단을 `analyze_product`에 위임 |
| Product ReAct | 비교 항목 선택, 카탈로그 식별 요청, `compare_products` 호출 |
| Catalog Planner + Python | 원문의 비교 대상을 분리하고 상품명·코드 대응 확인 |
| 도구 내부 Python 검색 | 상품별 문서 범위 검색, 실행 예산·근거·부분 실패 관리 |
| 도구 내부 비교 HCX | 독립 입력에서 비교 답변·조건 작성, 사용 근거 선택 |
| Python 결과 조립 | 구조화 응답 파싱, 실제 청크 ID 연결, 완료 답변과 출처 보존 |

비교 작성은 도구 내부의 HCX-007, Thinking `none` 생성 역할이 소유한다. 답변을 만든 뒤
Product의 `submit_domain_result`로 돌아가지 않고 같은 Product 실행을 완료한다.
비교 셀·셀별 상태·coverage 산출, 답변 내용·인용 의미 검증과 검증 실패 후 재작성은
이번 경로에 두지 않는다. 실행 입력, 응답 형식과 근거 ID를 처리하는 기본 계약은 유지한다.
자동 상품 선정·전체 카탈로그 순위화, 개인 포트폴리오 최적화는 범위에 포함하지 않는다.

## 2. 선행 계약: 복수 대상 식별

각 모델 응답에서 `return_product_catalog_query`를 정확히 한 번 호출하는 규칙은 유지한다.
Query union의 `resolve_products` route 안에 대상 배열을 담는다.
기존 단일 상품·전체/운용사 목록 route는 유지한다.

Product는 비교 요청의 `lookup_product_codes` 호출에 선택적 입력 `comparison_criteria`를
지정한다. Python이 3절의 enum·개수·중복을 검증한 뒤 Planner를 호출하고, 복수 식별 성공 시
대상과 항목을 state에 저장한다. 복수 route에는 이 입력이 필수이며, 단일 상품·목록 조회는
기존 무인자 호출을 유지한다. 따라서
0~1개 식별로 비교를 실행하지 않아도 요청 항목을 보존한다. 카탈로그 코드 오선택에는
아래의 제한된 Planner 교정만 허용한다. 이 식별 교정은 비교 답변 재작성과 별개다.

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
  전에 상한 오류로 종료하고 일부를 버리지 않는다.
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
원래 요청의 제한으로 함께 보존한다. 0~1개이면 비교 Tool을 호출하지 않고 Python이
대상 식별 부족을 설명하는 `undetermined` 결과를 생성한다. 개별 상품 사실을 추가 검색해
비교 완료로 표시하지 않는다. 동일 코드의 반복 표현은 target 연결을
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
| `criteria` | 중복 없는 아래 enum 배열, 1~3개, state의 `comparison_criteria`와 순서까지 일치 |
| ToolRuntime | 질문 원문, 전체 targets, catalog version, 상위 deadline과 실행 상태 자동 주입 |

| criterion | 비교 범위 |
|---|---|
| `investment_strategy` | 투자 대상·비중, 만기·듀레이션, 비교지수와 운용 방식 |
| `risk` | 공시 위험등급·위험지표·금리 등 가격변동 위험 |
| `capital_protection` | 원금보장 여부, 원금손실 가능성, 예금자보호 |
| `fees` | 보수·비용·판매/환매수수료의 종류, 클래스와 적용 조건 |
| `liquidity` | 환매 절차·지급 시점·제한, 보유기간 관련 조건 |

질문에 필요한 최소 항목을 선택한다. 안정성만 묻는 질문에는 `risk`와 `capital_protection`,
일반적인 차이와 안정성을 함께 묻는 질문에는 `investment_strategy`까지 3개를 선택하도록
지시한다. 특정 한 항목만 요청하면 하나만 비교하며, `fees`와 `liquidity`는 명시 요청에만
선택한다. 세 항목을 채우기 위한 자동 확장은 하지 않는다.

3개 상한은 두 Tool의 모델 노출 스키마, 카탈로그 입력, 검색 config가 함께
강제한다. 항목의 의미 선택은 HCX가 담당하며 Python 키워드 라우팅으로 대신하지 않는다.
명시 요청이 3개를 넘으면 핵심 항목을 우선하고 제외 항목을 결론·`missing_conditions`에
남겨 `conditional`로 답하도록 비교 생성기에 지시한다. 제외 항목의 식별·누락 방지는 프롬프트의 책임이며
Python이 원문 요청 전체와 선택 항목의 의미 대응까지 검증하지는 않는다. 검색 표현은
`prompts/domain/product-comparison-search.json`에서 버전 관리한다.

모델은 파일명·문서 ID·검색 개수·정렬·timeout을 입력하지 않는다. 추가 필드는 금지한다.
미등록 코드, 확정 대상의 임의 추가·누락, 중복 코드, 개수 초과, 잘못된 criterion은 검색 전에
거절한다. 개수가 많다는 이유로 앞의 일부만 자동 선택하지 않는다.

## 4. 상품별 검색과 독립 생성 입력

기존 `ProductComparisonService`는 비교 대상마다 공식명과 선택한 항목의 검색 표현을
합친 질의를 한 번씩 병렬 실행한다. 검색은 해당 상품의 투자설명서 범위로 제한하고
`Permission.PRODUCT`를 적용한다. Search Service와 embedding·Qdrant의 공통 제한을 사용한다.

검색 service의 내부 결과는 실행 상태, catalog version, 전체 targets, criteria,
상품별 `attempts`와 고유 `evidence`, 검색 제한을 보존한다. 성공한 시도의 청크만 생성기에
전달한다. 전체 검색 결과와 내부 시도 기록을 Product의 다음 모델 입력으로 반환하지 않는다.

비교 생성기는 전용 system prompt와 다음 정보를 담은 새 요청 메시지를 받는다.

| 정보 | 처리 |
|---|---|
| 질문 원문·판단 목표 | 원래 입력을 보존 |
| 카탈로그 버전·전체 대상·비교 항목 | 공식명·상품 코드·원문 표현·미식별 상태 포함 |
| 상품별 검색 상태·근거 ID·제한 | 일부 실패나 미식별 대상을 숨기지 않음 |
| 고유 근거 | 청크 ID·출처·제목·위치·원문을 한 번씩 전달 |

전체 카탈로그, Product의 이전 AI/Tool 메시지, 과거 비교 답변은 전달하지 않는다. 원문은
ID로 중복 제거하고 상품별 참조 관계를 보존한다. 같은 ID는 처음 나온 청크를 사용하며
동일 ID의 원문·출처가 서로 다른지 추가 검사하지 않는다. 고유 청크를 요약하거나 문자열 길이로 자르지 않으며, 입력 토큰
상한이나 상품별 청크 예산은 이번 범위에 추가하지 않는다. 문서는 근거 데이터로 전달한다.

한 번의 검색 batch 이후 자동 보완 검색은 수행하지 않는다. 기존 service의 보완 검색
구현이 남아 있더라도 현재 비교 경로에서는 호출하지 않는다.

| 검색 결과 | 처리 |
|---|---|
| 모든 확정 상품에서 근거 확보 | 전체 근거를 생성기에 전달 |
| 일부 상품에서 근거 확보 | 확보한 근거와 실패·누락 상태를 함께 전달 |
| 완료한 검색은 있으나 근거가 전혀 없음 | 생성 호출 없이 근거 부족 안내와 `undetermined` 결과 |
| 모든 검색이 timeout | Product timeout, 정제된 오류 |
| 성공한 검색 없이 실패가 하나 이상 | Product failed, 정제된 오류 |
| 입력 계약 위반 | 검색 전에 failed, 입력을 임의로 바꿔 우회하지 않음 |

내부 `retrieval_coverage`가 남아 있어도 검색 대상 중 청크 존재 여부를 나타낼 뿐이다.
비교 답변의 정확성·항목 충족·완성도를 계산하거나 `complete`를 주장하는 값으로 사용하지 않는다.

## 5. 생성 결과와 책임 경계

비교 생성기는 `submit_comparison_answer`를 한 번 호출해 `answer`, `status`,
`missing_conditions`, `warnings`, `evidence_chunk_ids`를 구조화된 응답에 담는다. Python은 이 응답을 파싱하고 선택된 ID를 실제 검색 청크에 연결해
`DomainResult`를 구성한다.

```text
DomainResult {
  domain: "product",
  execution_status: "completed",
  comparison_answer: string,
  decision: { status, conclusion, missing_conditions },
  evidence: 실제 선택된 검색 청크[],
  calculations: [],
  warnings: string[]
}
```

`comparison_answer`는 사용자에게 전달할 완성된 답변이다. 내부 Domain 계약의 선택적
필드이며 외부 API 필드를 늘리지 않는다. 다른 Domain이나 실패 결과에 비교 답변을
붙이지 않는다. 식별 부족 안내에는 기존 결정론적 `comparison_result`의 미확인 셀이
남으며 모델 답변을 심사하는 데 사용하지 않는다. 검색 근거가 없으면 정해진 안내 문장을
`comparison_answer`에 담는다. 단일 상품·카탈로그 경로는 기존 제출 방식을 사용한다.

생성기는 원문이 설명하는 상품·모펀드/자펀드·클래스·기준시점·예외를 구분하고,
확인되지 않은 사실을 추정하지 않도록 지시받는다. 과거 변경 이력을 현행 조건으로
단정하지 않으며, 단위·상한·적용 조건을 보존한다. 미비교 항목과 확인이 필요한 조건을
답변에 밝히도록 한다. 이러한 지시의 준수 여부는 별도 평가 대상이다.

현재 경로가 수행하는 처리는 다음으로 한정한다.

- Tool 입력의 상품 식별·개수·항목·순서 확인.
- 구조화 모델 응답의 필수 필드·타입과 기본 Domain 계약 파싱.
- 모델이 선택한 근거 ID 중 해당 실행에서 확보한 실제 청크에 일치하는 항목만 연결.
  존재하지 않는 ID는 최종 근거에서 제외하며 답변을 거절하거나 다시 쓰지 않음.
- 동일 청크 중복 제거, 실행 상태·시간 제한·오류와 취소 처리.

대상×항목 셀을 요구하거나 셀 상태별 인용 수를 검사하지 않는다. 답변의 주장과 원문이
의미상 일치하는지, 모든 요청 항목을 설명했는지, 추천이 적절한지 판단하는 검증기를 두지
않는다. 구조화 응답 형식에 실패하면 정제된 실패로 종료하며, 내용을 고치도록 다시
생성시키거나 이전 Product 제출 경로로 되돌리지 않는다. 존재하지 않는 ID가 모두 제외되어
선택 근거가 비어도 그 이유만으로 작성된 답변을 거절하지 않는다.

도구는 수익률 차이·비용·위험값을 새로 계산하지 않는다. 계산 요구가 섞이면
[공통 계산 계약](../../../PROJECT_RULES.md)을 따른다. 기존 단일 상품용 Calculation Tool을
복수 후보 state에 그대로 적용하지 않으며, 수행하지 못한 계산 요구는 조건으로 남긴다.

## 6. 실행 순서와 예산

```text
Main → analyze_product
  → Product: lookup_product_codes(comparison_criteria)
  → Catalog Planner의 resolve_products 계획 1개 + Python 상품 식별 확인
  → Product: compare_products(확정 코드 전체, 저장한 항목)
      → 상품별 SearchService.search 한 batch 병렬 실행
      → 고유 원문과 최신 검색 상태로 독립 입력 구성
      → 전용 HCX가 비교 답변 한 번 생성
      → 구조화 응답 파싱 + 선택 근거 ID 연결
      → Product DomainResult 완료
  → Main → AnswerService가 완료 답변과 출처 보존 → API
```

복수 대상 식별 후 Product에는 `compare_products` 실행만 허용한다. 이전 Tool 메시지를
해석하기 위한 schema를 포함하더라도 해당 Tool을 다시 실행할 수는 없다. 비교 Tool이
완료되면 Product 모델을 다시 호출하지 않는다. 단일 상품·카탈로그 경로의 Tool 순서는 유지한다.

| 항목 | 기본값 |
|---|---|
| 전체 target / criteria 상한 | 5 / 3, 미식별·반복 target도 포함 |
| `lookup_product_codes` / `compare_products` | 요청당 각각 1회 |
| Catalog Planner | 기본 1회, 유일 후보와 코드 불일치 교정에만 최대 1회 추가 |
| 최초 Search Service 호출 | 확정 상품 N개에 대해 N회 |
| 비교 보완 검색 | 현재 실행 경로에서는 0회 |
| 비교 검색 / 생성 예약 | 최대 30초 / 30초 예약 |
| Product ReAct | 기존 최대 5회, 비교 생성 이후 재호출 없음 |
| 전용 비교 생성기 | 논리적 생성 1회, 내용 수정·재작성 재시도 없음 |
| 생성 모델 / 최대 출력 | HCX-007, Thinking `none` / 4096 |
| Product ReAct / Catalog Planner 최대 출력 | 기존 4096 / 1024 유지 |
| 동시성 / 상위 deadline | 기존 프로세스 제한, Domain 75초·API 180초 유지 |

비교 검색 마감은 진입 시 `min(현재 시각 + 30초, Domain deadline - 30초)`로 정하고
연장하지 않는다. 대기·embedding·Qdrant·검색 재시도 모두 이 마감을 공유한다. 남은 검색
시간이 없으면 새 검색을 시작하지 않는다. 남은 task는 취소·회수한다.

전용 생성기는 별도 모델 인스턴스와 `PRODUCT_COMPARISON_ANSWER_HCX_CONFIG`를 사용하며
호출당 timeout은 30초, SDK retry는 0회다. 공통 HCX 용량 제한과 같은 Domain deadline을
공유한다. 429에 대한 공통 인프라 재시도는 최대 한 번의 추가 물리 호출을 허용한다. 이는 생성 결과를 검사한
후 답변을 다시 쓰는 재시도가 아니다. 파싱·내용 실패를 교정하는 추가 생성은 하지 않는다.

30초 예약은 생성 성공을 보증하지 않는다. 부모 deadline이나 외부 취소가 먼저 발생하면
전파한다. 부모 timeout이면 기존 GuardedDomainRunner의 근거 없는 timeout 계약을 따르므로,
부분 근거는 부모 마감 전에 정상적으로 결과를 완료한 경우에 보존된다.

## 7. Main·API와 추적

Main용 Domain Tool 결과에는 기존 `decision`과 `comparison_answer_ready=true`를 전달한다.
전체 근거는 state의 DomainResult에 보존하며 Main 모델 입력에는 넣지 않는다. 본문을 두
필드에 반복하지 않으며 AnswerService는 원래 DomainResult의
`comparison_answer` 본문을 그대로 보존하고 실제 선택된 근거의 출처를 덧붙인다. Product가 완료한
답변을 다른 모델이 새로 쓰거나 비교표로 재구성하지 않는다. 조건과 경고도 최종 결과에
보존한다. 복합 질문에서는 다른 Domain 결과와 함께 결정론적으로 조립하고, 다른 Domain의
기존 계산·숫자 처리 계약을 유지한다.

최종 `retrieved_context`에는 생성기가 실제로 선택한 청크만 넣는다. Python이 답변의 모든
문장과 선택 청크의 의미 대응까지 확인했다는 뜻은 아니다. 외부 `/answer`의 필드는
`question_id`, `question`, `retrieved_context`, `think_trace`, `answer` 5개를 유지한다.

LangSmith는 [개인 추적 정책](../../operations/langsmith-tracing.md)을 따른다. 기존 요청 아래
Product의 식별·도구 선택, `compare_products`의 검색과 독립 생성 호출을 추적한다.
상품별 검색 횟수·상태·시간, 입력량, 생성 역할의 물리 호출 수, 사용 근거와 최종 답변을
구분한다. 문자 수를 정확한 입력 토큰 수로 표현하지 않으며 provider 사용량을 별도로 기록한다.
HTTP 200이나 trace 오류 없음만으로 답변 품질 성공을 집계하지 않는다.

## 8. 구현 확인과 품질 평가

| 사례 | 확인할 동작 |
|---|---|
| 등록된 3상품 비교 | 계획 1개, 정확한 코드·항목 유지, 상품별 검색과 독립 생성 |
| 3대상 중 2개 / 1개 / 0개 식별 | 일부 미식별 상태 전달 / 비교 미실행 / 비교 미실행 |
| 잘못된 코드·중복·대상 추가/누락·상한 초과 | 검색 전 거절, 임의 부분 선택 없음 |
| 일부 검색 실패·빈 성공·모든 실패 | 4절 상태와 근거·제한 보존 |
| 독립 입력 | 이전 Product AI/Tool 메시지 없음, 고유 원문과 상품별 참조 관계 유지 |
| 생성 성공 | Product 추가 모델 호출·비교 submit·자동 보완 검색 없음 |
| 응답 형식 오류 | 내용 교정 호출 없이 정제된 실패 |
| 존재하지 않는 선택 근거 ID | 해당 ID는 근거에서 제외, 답변 거절·교정 호출 없음 |
| provider 일시 오류·취소·deadline | 공유 제한 안의 인프라 재시도, 부모 취소 전파 |
| Main/API | 비교 본문·조건·출처와 혼합 Domain 결과 보존, API 정확히 5필드 |
| 단일 상품·카탈로그 | 기존 검색·계산·제출 동작 유지 |

단위·통합 테스트는 실행 경로와 데이터 계약을 확인한다. 실제 HCX 답변에 대해서는 항목
누락, 모·자펀드나 클래스 혼동, 인용 의미, 조건·예외 보존, 완료율과 지연을 별도로 평가한다.
이번 경로에는 그 품질 판정을 온라인에서 자동 적용하는 검증 로직을 추가하지 않는다.
개인 질문 원문, LangSmith 링크·workspace ID, 인증값은 공용 문서에 기록하지 않는다.

구현 확인은 `tests/unit/agent/test_product_comparison.py`,
`test_product_comparison_answer.py`, `test_comparison_contracts.py`, `test_domain_agents.py`에서
검색·독립 생성·결과 보존·기존 경로를 나눠 수행한다.
