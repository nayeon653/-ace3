# Product Agent 스펙

## 목적과 책임

Product Agent는 검증된 상품 카탈로그를 조회하고 개별 상품 및 명시적인 복수 상품의 특성,
비용, 위험과 유동성을
투자설명서 근거로 판단한다. 카탈로그의 상품명·운용사·코드만으로 상품의 우수성이나 개인
적합성을 판단하지 않는다.

## 모델과 구현

| 항목 | 값 |
|---|---|
| ReAct 모델 | `HCX-007`, Thinking `none` |
| Catalog Planner 모델 | `HCX-007`, Thinking `none` |
| 공통 생성 설정 | temperature `0.1`, 호출당 30초, retry 2회 |
| 최대 생성 토큰 | Product ReAct `4096`, Catalog Planner `1024` |
| 프롬프트 | `pension_agent/prompts/domain/product-agent.md` |
| 구현 | `pension_agent/agent/product/` |

Product ReAct와 Catalog Planner는 같은 프로세스 HCX 동시성 제한을 공유하지만 별도 모델
인스턴스를 사용한다.

## 입력과 출력

입력은 `DomainRequest {question, objective}`다. 출력은 `domain=product`인 공통
`DomainResult`다. 상품 카탈로그 개수·목록 조회에는 추가로 검증된 `catalog_result`가
포함된다. 명시적인 복수 비교에는 전체 대상·항목·셀·제한을 가진 `comparison_result`가
포함되며 `catalog_result`와 함께 넣을 수 없다.

## Tool

### `lookup_product_codes`

Product Catalog Query Planner에 질문 원문과 판단 목표를 전달하고 전체 카탈로그에 근거한
계획 하나를 받는다. Python이 계획을 같은 카탈로그 스냅샷으로 다시 검증하고 실행한다.

가능한 결과는 다음과 같다.

- 단일 상품 코드 식별
- 명시적인 2~5개 비교 대상 식별: 확정·모호·미등록 상태를 대상별로 보존
- 전체 또는 공식 운용사별 개수·목록 조회
- 상품 미등록 또는 모호함
- 운용사 미등록
- Planner 실패 또는 timeout

복수 비교에서는 `comparison_criteria`에 중복 없는 1~5개 비교 항목을 지정한다.
Planner는 `resolve_products` 계획 하나를 반환하며 Python이 원문 조각과 공식명·alias의
대응을 검증한다. 확정된 서로 다른 코드가 0~1개이면 검색 없이 모든 요청 셀을 미확인으로
보존한 `undetermined` 결과를 생성한다.

### `compare_products`

- 카탈로그 조회가 확정한 코드 전체와 순서를 `product_codes`로 전달한다.
- `criteria`는 조회 때 저장한 비교 항목과 순서까지 같아야 한다.
- 2~5개 상품의 투자설명서를 같은 항목으로 한 번씩 병렬 검색한다.
- 상품별 `attempts`, 성공한 원문 근거, 미식별 대상과 검색 오류를 분리해 반환한다.
- 도구 내부의 생성 LLM 호출은 없으며 기존 Search Service와 provider 제한을 공유한다.
- 비교 전체는 요청당 한 번만 실행하며 검색 근거를 확보한 후 Product HCX가 해석한다.
- state에는 시도별 전체 `SearchResult`를 보존한다. 모델 ToolMessage에서는 시도 안의
  중복 원문만 생략하고 상품별 `evidence`에 유지하며, 시도 상태·오류·제한도 전달한다.
- ToolMessage의 `next_step`은 비교 셀 제출 안내이며 내부 service 결과 모델이나 API 필드가
  아니다.

입출력·상태표·비교 셀·예산의 상세 계약은
[Product 상품 비교 도구](../components/product-comparison.md)를 따른다.

### `search_documents`

- `fund_prospectus` 문서만 검색한다.
- 단일 상품 식별 후에는 검증된 `product_code`를 실제 원본 파일명으로 변환해 문서 범위를
  제한한다.
- 상품 식별 전 일반적인 판단 기준을 찾을 때만 상품 코드 없이 전체 검색할 수 있다.
- 검색 입력은 판단할 비용·위험·유동성·운용 특성을 나타내는 구체적인 `objective`다.
- 첫 검색이 부족하면 최대 한 번 다른 문서 표현으로 다시 검색할 수 있다.
- 비교 경로에서는 최초 `compare_products` 이후에만 확정된 상품 코드로 보완 검색한다.
  전체 보완은 최대 2회, 상품별로 최대 1회이며 최초 검색 마감을 연장하지 않는다.

### `calculate_fund_standard_price`

- 단일 상품 문서 검색 후 자산총액, 부채총액과 총좌수가 확인된 경우에만 실행한다.
- Calculation Service의 `fund_standard_price`만 호출하며 한 번으로 제한한다.

### `calculate_fund_var_risk`

- 단일 상품 문서 검색 후 일간 2.5퍼센타일 손실률이 확인된 경우에만 실행한다.
- Calculation Service의 `fund_var_risk`만 호출하며 한 번으로 제한한다.

### `calculate_fund_reported_var_risk`

- 단일 상품 문서 검색 후 결과값으로 공시된 연환산 97.5% VaR가 확인된 경우에만 실행한다.
- 공시값을 그대로 `fund_reported_var_risk`에 전달하며 다시 연환산하거나 반올림하지 않는다.
- 식별된 단일 `product_code`의 문서와 질문의 명시적 클래스가 source와 일치해야 한다.
- 현재·최신 값 요청은 검색 순위가 아니라 신뢰 가능한 공시일 metadata로 최신성을 확인해야 한다.
  현재 검색 청크 계약에는 공시일 metadata가 없으므로 최신성 요구가 있으면 계산을 차단하고
  `최신 공시 기준일 확인 필요`를 누락 조건으로 남긴다.
- 연환산 여부가 불명확하거나 일간 VaR·변동성·표준편차·위험등급 숫자만 확인되면 실행하지
  않는다.

### `calculate_fund_frontend_sales_fee`

- 단일 상품 문서 검색 후 검증된 상품·클래스의 납입금액과 선취판매수수료율이 확인된 경우에만
  실행한다.
- 요율이 여러 클래스나 보유기간 구간으로 나뉘어 있으면 질문 조건과 정확히 일치하는 요율 하나만
  선택한다. 클래스나 구간이 여럿이고 질문에 명시가 없으면 실행하지 않는다.
- 요율이 고정인지 "이내"·"상한" 표현의 상한인지 `rate_kind`로 구분해 전달한다.
- Calculation Service의 `fund_frontend_sales_fee`만 호출하며 한 번으로 제한한다.

### `calculate_fund_deferred_sales_fee`

- 단일 상품 문서 검색 후 검증된 상품·클래스·보유기간의 환매금액과 후취판매수수료율이 확인된
  경우에만 실행한다.
- 후취판매수수료율이 보유기간 구간별로 다르면 사용자 보유기간과 문서의 구간 표현이 정확히
  일치하는 요율만 사용한다.
- 요율이 고정인지 "이내"·"상한" 표현의 상한인지 `rate_kind`로 구분해 전달한다.
- Calculation Service의 `fund_deferred_sales_fee`만 호출하며 한 번으로 제한한다.

### `calculate_fund_redemption_fee`

- 단일 상품 문서 검색 후 검증된 상품·클래스·보유기간의 이익금과 환매수수료율이 확인된 경우에만
  실행한다.
- 환매수수료율이 보유기간 구간별로 다르면 사용자 보유기간과 문서의 구간 표현이 정확히 일치하는
  요율만 사용한다.
- 요율이 고정인지 "이내"·"상한" 표현의 상한인지 `rate_kind`로 구분해 전달한다.
- Calculation Service의 `fund_redemption_fee`만 호출하며 한 번으로 제한한다.

세 수수료 Tool은 선취판매수수료·후취판매수수료·환매수수료를 서로 다른 계산으로 다루며 총보수·
운용보수·판매보수·신탁보수·기타비용·총비용비율(TER)의 수치를 요율로 사용하지 않는다. 고정
요율이면 `fee_amount_krw`, 상한 요율이면 `maximum_fee_amount_krw`만 반환하며, 실제 적용
요율이 확인되지 않고 상한 요율만 문서에 있으면 상한 계산 결과는 보존하되 실제 적용 수수료율을
누락 조건으로 남기고 상한 결과를 실제 부과금액처럼 서술하지 않는다.

여섯 Tool 모두 사용자 질문 또는 검증된 검색 근거에 없는 입력을 추정하지 않는다. 각 입력은
필드명, 값 하나와 단위를 포함한 원문 `source` 구절을 함께 제출하며, Python이 필드 의미,
구절 포함 여부와 정규화 수치 일치를 검증한다. 검색 청크에서 가져온 입력은 해당 `chunk_id`를
계산 결과에 기록하고 최종 evidence에 자동 포함한다. 계산한 결과는 state에서 직접
`DomainResult.calculations`로 전달하고 자유 형식 제출값으로 받지 않는다.
복수 상품 비교 state에서는 이 단일 상품용 계산 Tool들을 노출하지 않는다.
복합 질문에서 일부 계산만 성공하면 성공한 계산 결과를 보존하되 전체 상태를 강제로
`determined`로 바꾸지 않고, 계산하지 못한 항목의 `missing_conditions`를 유지한다.

### `submit_domain_result`

검색 근거 판단은 실제 사용한 청크 ID와 함께 제출한다. 카탈로그 개수·목록 결과는
`status=determined`, 빈 `missing_conditions`, 빈 `evidence_chunk_ids`로 제출한다.

카탈로그 제출의 빈 `evidence_chunk_ids`는 모델이 Qdrant 청크를 선택하지 않는다는 뜻이다.
최종 `DomainResult`에는 Python이 `product_catalog.json` 조회값을 직렬화한 결정론적 근거
한 개를 자동으로 포함한다. 이 근거에는 route, 운용사, 반환 방식, 정확한 개수·목록과
`catalog_version`이 기록된다.

비교 제출은 `comparison_cells`에 전체 대상×항목의 상태, finding, 상품 코드·청크 ID 참조,
제한을 담는다. Python이 상품별 성공 검색과 참조를 대조하고 실제 인용 청크만 최종 evidence로
보존한다. coverage는 Python이 계산하며 `partial`은 `conditional`, `none`은 `undetermined`로
강제한다. 미확인 셀이나 근거가 전혀 없는 비교의 자유 생성 내용을 최종 사실로 채택하지 않는다.

## 실행 경로

### 카탈로그 개수·목록

```text
lookup_product_codes
  -> Catalog Planner 계획 검증
  -> Python 카탈로그 조회
  -> submit_domain_result
  -> catalog_result + 결정론적 catalog evidence
```

이 경로에서는 투자설명서를 검색하지 않고 특정 상품을 추천하지 않는다.

### 특정 상품 판단

```text
lookup_product_codes
  -> 단일 product_code 확정
  -> 해당 상품 문서 search_documents
  -> 필요 시 검색 목표를 바꿔 1회 추가 검색
  -> 기준가격, 공시 연환산 VaR, 일간 VaR 또는 수수료 계산이면 의미에 맞는 Calculation Tool 하나
  -> submit_domain_result
```

상품이 없거나 모호하면 문서를 검색하지 않고 `undetermined` 또는 `conditional`로 안전하게
종료한다. 질문이 서로 다른 계산을 함께 요구하면(예: 선취판매수수료와 환매수수료를 모두 묻는
경우) 각 Calculation Tool은 실행당 한 번으로 제한되므로, 서로 다른 계산 Tool을 이 단계에서
차례로 각각 한 번씩 호출한 뒤 제출한다. 같은 Tool을 다시 호출하지는 않는다.

### 일반 상품 판단 기준

```text
product_code 없는 전체 search_documents
  -> lookup_product_codes로 질문과 카탈로그 대조
  -> 단일 상품이면 상품 범위 재검색
  -> submit_domain_result
```

전체 검색 결과만으로 특정 상품을 임의 선택하거나 최종 상품 근거로 제출할 수 없다.

### 명시적인 복수 상품 비교

```text
lookup_product_codes(comparison_criteria)
  -> resolve_products 계획 1개, 원문 표현·코드 검증
  -> compare_products(확정 코드 전체, 저장된 항목)
  -> 필요 시 특정 상품의 search_documents 보완
  -> 모든 대상×항목의 comparison_cells 제출
  -> 검증된 comparison_result와 실제 인용 근거
```

모든 상품 검색이 실패·timeout이면 동일 상태로 종료한다. 완료 시도가 있지만 청크가
전혀 없으면 원래 대상·항목과 검색 제한을 보존한 `undetermined` 결과를 생성한다.

## Tool 순서 강제

Middleware는 한 모델 응답에서 현재 단계에 허용된 Tool 호출 하나만 남긴다.

- 특정 상품 식별 전 상품 코드가 있는 검색을 거부한다.
- 식별된 후보 코드와 다른 상품 코드 검색을 거부한다.
- 카탈로그 조회 후에는 정해진 확정 제출만 허용한다.
- 단일 상품 식별 후 상품 범위 검색 전 최종 제출을 거부한다.
- 상품 범위 검색 전 Calculation Tool 호출을 거부한다.
- 공시 연환산 VaR 근거가 있으면 일간 VaR Tool 호출을 거부하고 reported Tool만 허용한다.
- 질문 클래스와 source 클래스가 다르거나 최신 공시를 확정할 metadata가 없으면 reported
  Tool 호출을 거부한다.
- Calculation Tool과 제출을 동시에 요청하면 계산을 먼저 실행하고, 성공 후에는 제출만
  허용한다.
- 한 모델 응답의 결과 제출은 하나로 제한한다.
- 복수 식별 후에는 확정된 전체 코드와 저장한 항목의 `compare_products`만 허용한다.
- 최초 비교 검색 후에는 확정된 상품의 보완 검색 또는 비교 셀 제출만 허용한다.

비교 state에만 모델 호출 전 Tool schema 필터를 추가로 적용한다. 현재 실행 가능한 Tool과
이전 Tool 메시지 해석에 필요한 schema를 유지하고, 최초 비교에는
`tool_choice=compare_products`를 사용한다. 검색 후에는 지정 생략(`tool_choice=None`, 기본
auto)으로 보완 검색을 선택할 수 있게 한다. 가장 최근 AIMessage의 Tool 호출이 비어
재지시했거나 검색 상한으로 제출만 허용되면 `tool_choice=submit_domain_result`로 구조화
제출을 강제한다. 빈 호출에는 자유 문장과 불허 호출 제거 결과가 포함된다. 과거 Tool의 재실행은 기존
순서·횟수 검사로 거절한다. 비교 state가 없는 단일 상품·카탈로그 경로에는 이
필터와 Tool 선택 강제를 적용하지 않는다.

## 실행 제한

| 제한 | 값 |
|---|---:|
| Product ReAct 모델 호출 | 최대 5회 |
| Catalog Tool | 최대 1회 |
| Catalog Planner 모델 | 기본 1회, 복수 후보·코드 대응 교정에만 최대 1회 추가 |
| 단일 상품 검색 Tool | 최대 2회 |
| 비교 Tool | 최대 1회, 실제 최초 검색은 상품별 N회 |
| 비교 보완 검색 | 전체 최대 2회, 같은 상품 최대 1회 |
| 비교 대상 / 항목 / 셀 | 최대 5개 / 5개 / 25개 |
| 비교 검색 마감 | `min(진입 시각 + 30초, Domain deadline - 30초)` |
| 기준가격 Tool | 최대 1회 |
| 공시 연환산 VaR Tool | 최대 1회 |
| 일간 VaR 위험등급 Tool | 최대 1회 |
| 선취판매수수료 Tool | 최대 1회 |
| 후취판매수수료 Tool | 최대 1회 |
| 환매수수료 Tool | 최대 1회 |
| 제출 Tool | 최대 2회 |
| 실행 deadline | 75초 또는 상위 deadline 중 빠른 시각 |
| 동시 실행 | 프로세스당 3개 |

## 호환 경로

`catalog_matcher.py`와 `product-catalog-matcher.md`는 주입형 단위 테스트와 이전 호출 계약을
위한 legacy 호환 경로다. 운영 런타임은 `HCXProductCatalogQueryPlanner`를 사용한다. 두
구현을 동시에 주입할 수 없다.

## 현재 제한

- 과거 수익률이나 개인 포트폴리오 기반 적합성 계산을 수행하지 않는다.
- 여러 상품의 의미적 순위를 자동 산출하지 않는다.
- 투자설명서와 카탈로그에 없는 매수 가능 여부를 추정하지 않는다.

## 검증 위치

- `tests/unit/agent/test_domain_agents.py`
- `tests/unit/agent/test_product_catalog_query.py`
- `tests/unit/agent/test_product_catalog_matcher.py`
- `tests/unit/agent/test_product_comparison.py`
- `tests/unit/agent/test_comparison_contracts.py`
- `notebooks/agent/product_agent_playground.ipynb`
