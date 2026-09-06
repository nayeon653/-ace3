---
status: superseded
date: 2026-09-05
type: architecture
related:
  - 20260905-all-generation-hcx-007.md
  - 20260820-80-router-search-service.md
supersedes: []
superseded-by:
  - 20260906-product-comparison-minimal-criteria.md
  - 20260906-product-comparison-answer-ownership.md
  - 20260906-product-catalog-selection-retry.md
  - 20260906-product-comparison-free-query.md
---

# 상품 비교의 검색 예산과 Product 출력 상한을 분리한다

## 배경

명시적인 복수 상품 비교는 2~5개 대상과 1~5개 항목을 다룬다. Product는 최대 25개 셀에
각각 대상 ID, 비교 항목, 확인 상태, finding, 상품 코드·청크 ID 참조, 제한을 제출해야 한다.
조건별 결론과 누락 조건도 함께 제출하므로 기존 단일 상품용 1024 출력 토큰 상한에서는
구조화 결과가 잘리거나 필요한 셀과 근거를 생략할 위험이 있다.

검색 대상을 늘리면서 기존의 단일 상품 검색 최대 2회를 그대로 적용하면 초기 비교를
완료하지 못한다. 반대로 검색 횟수나 마감을 늘리기만 하면 최종 Product 제출을 위한
시간이 부족해질 수 있다.

내부 결과의 시도별 청크와 누적 근거를 모두 모델 메시지에 직렬화하면 같은 원문을 중복해서
전달하게 된다. 또한 비교 근거를 수집한 이후에는 자유 문장 대신 구조화 셀 제출이 필요하므로
모델에게 전달할 Tool과 다음 동작도 비교 단계에 맞게 제한해야 한다.

## 결정

`PRODUCT_REACT_HCX_CONFIG.max_tokens`를 1024에서 4096으로 늘린다. Product ReAct의
모든 호출에 같은 설정을 적용하며, 비교 여부에 따른 별도 모델 인스턴스를 만들지 않는다.
모델은 `HCX-007`, Thinking은 `none`, temperature는 `0.1`을 유지한다. Main과 Catalog
Planner를 비롯한 다른 역할의 출력 상한은 1024를 유지한다. Product 모델 호출 최대 5회,
provider 호출당 30초와 retry 2회도 유지한다.

비교 검색의 실행 상한은 별도 불변 `ProductComparisonConfig`에서 관리한다.

| 항목 | 기본값 |
|---|---:|
| 전체 비교 대상 / 비교 항목 | 5개 / 5개 |
| 최초 검색 | 확정된 서로 다른 상품별 1회 |
| 보완 검색 | 전체 최대 2회, 상품별 최대 1회 |
| 검색 마감 | 비교 진입 시각 + 30초와 Domain deadline - 30초 중 빠른 시각 |
| Domain deadline | 기존 75초 또는 부모 deadline 중 빠른 시각 |

검색 마감은 최초·보완 검색이 함께 사용하며 다시 계산해 연장하지 않는다. 검색 호출은
기존 Search Service와 embedding·Qdrant의 프로세스 동시성 제한을 공유한다. 최초 batch를
한 번의 실제 검색으로 집계하지 않으며 실패 시도도 상품별 attempts와 예산에 남긴다.

Catalog Planner의 복수 계획에서 모든 원문 조각이 유효하고 `single` 대상마다 후보가
유일한데 코드만 불일치하면 같은 모델에 최대 한 번의 교정을 허용한다. 원래 대상과 상태를
유지한 전체 계획을 재제출시키고 다시 검증한다. 후보 metadata를 피드백으로 주지만 Python이
코드를 자동 대체하지는 않는다. 원문·형식 오류나 후보 모호함에는 교정을 적용하지 않는다.
초기 계획과 교정은 같은 Domain deadline과 HCX 동시성을 사용하며 모델 호출 합계는 최대
2회다. 추가 사용량과 지연은 초기 호출과 구분해 평가한다.

출력 상한 확대로 새로운 생성 LLM 역할을 추가하지 않는다. 비교 Tool은 결정론적 Python
검색 수집만 맡고 기존 Product HCX가 근거를 해석한다. 근거 귀속과 모든 대상×항목 제출은
Python이 검증하고 최종 응답도 검증된 구조에서 조립한다.

내부 service 결과와 state에는 시도별 전체 `SearchResult`를 보존한다. 모델 ToolMessage에서만
`products[].attempts[].retrieved_chunks`를 제외하고 상품별 누적 `evidence`에 원문을 한 번
남긴다. 검색 상태·오류·제한은 유지하며, 메시지 전용 `next_step`으로 비교 셀 제출을 안내한다.
`next_step`을 내부 결과 모델이나 외부 API 필드로 추가하지 않는다.

비교 state의 모델 호출에만 현재 실행 가능한 Tool schema와 과거 Tool 메시지 해석에 필요한
schema를 남긴다. 최초 검색 전에는 `compare_products`를 지정하고 검색 후에는 지정을 생략해
(`tool_choice=None`, 기본 auto) 보완 검색을 선택할 수 있게 한다. 가장 최근 AIMessage의
Tool 호출이 비어 재지시했거나 검색 상한으로 제출만 허용되면 `submit_domain_result`를
이름으로 지정해 구조화 제출을 요구한다. 빈 호출에는 자유 문장과 불허 호출 제거 결과가 포함된다.
이전 Tool schema를 포함해도 기존 순서·횟수 검증이 재실행을 막는다.
단일 상품·카탈로그 경로의 Tool 선택 설정은 유지한다.

## 고려한 대안

- 1024토큰을 유지하면서 비교 셀이나 근거 참조를 줄이면 요청 항목과 출처를 보존하는 계약을
  약화시킨다. 상한 초과 시 조용히 앞의 일부 대상만 비교하는 방식도 채택하지 않는다.
- 모든 역할의 상한을 함께 늘리면 변경 영향이 불필요하게 커진다. 구조화 비교를 제출하는
  Product에만 적용한다.
- 별도 비교 LLM을 추가하면 새 호출·취소·동시성 경계가 필요하다. 기존 Product가 해석하고
  Python이 검색과 상태를 관리하는 구조를 사용한다.
- 검색에 Domain 시간 전체를 허용하면 검색 성공 후 결과를 제출하지 못할 수 있다.
  검색에 공통 마감을 두고 제출 시간을 예약한다.
- 모델 입력을 줄이기 위해 state에서 시도 원문을 삭제하면 근거 누적과 후속 제출 검증에
  필요한 기록을 잃는다. 메시지의 중복 표현만 줄이고 내부 기록을 보존한다.
- 일반적인 `tool_choice=required`는 현재 HCX 연결에서 유효한 파라미터로 받아들여지지
  않아 사용하지 않는다. 보완 검색 선택에는 `auto`, 특정 실행을 강제할 때는 Tool 이름을
  사용한다.

## 결과

- 최대 25셀과 상품별 출처·제한을 함께 제출할 출력 예산을 확보한다. 4096은 상한이며
  항상 그만큼 생성하도록 요구하지 않는다.
- 실제 출력 토큰과 지연이 늘어날 수 있다. 전체 질문과 최대 크기 입력에서 잘림, 셀 누락,
  근거 일치, 재시도, 지연을 따로 평가하며 이 결정에 실평가 성공을 전제하지 않는다.
- 메시지의 중복 원문 제거와 Tool 선택 강제는 입력량과 불필요한 자유 응답을 줄이기 위한
  장치다. provider 사용량 제한 해소나 구조화 제출 성공을 보증하지 않는다.
- 제출 여유 30초는 생성 성공을 보증하지 않는다. 부모 마감이나 외부 취소가 먼저 오면
  전파하고, 부분 근거는 부모 마감 전에 유효하게 제출한 경우에만 최종 보존된다.
- 4096에서도 최대 크기 제출이 반복해서 실패하거나 제출 여유가 부족하면 출력 계약의
  반복 필드·표현 길이와 검색 예산을 재검토한다. 대상이나 근거를 검증 없이 버리지는 않는다.

## 관련 자료

- [Product 상품 비교 도구 스펙](../specs/components/product-comparison.md)
- [Product Agent 스펙](../specs/agents/product-agent.md)
- [모든 생성 LLM을 HCX-007로 통일한 결정](20260905-all-generation-hcx-007.md)
- [비교 실행 config](../../pension_agent/config/product_comparison.py)
- [역할별 HCX config](../../pension_agent/config/hcx.py)
