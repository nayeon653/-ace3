# 제품 스펙

이 디렉토리는 현재 제품 런타임이 보장하는 외부 API와 Agent 동작의 기준 문서다.
아키텍처를 선택한 이유와 변경 이력은 `docs/decisions/`에, 실행 절차는
`docs/operations/`에 기록한다. 구현의 입출력·도구·제한·실패 동작이 바뀌면 같은 PR에서
이 스펙도 갱신한다.

## 스펙 목록

| 구분 | 문서 | 구현 주체 |
|---|---|---|
| 외부 API | [평가용 API](api.md) | `pension_agent/api/`, `AnswerService` |
| 상위 Agent | [Main Supervisor](agents/main-supervisor.md) | `agent/orchestration/` |
| Domain Agent | [Policy Agent](agents/policy-agent.md) | `agent/policy/` |
| Domain Agent | [Tax/Payout Agent](agents/tax-payout-agent.md) | `agent/tax_payout/` |
| Domain Agent | [Product Agent](agents/product-agent.md) | `agent/product/` |
| 보조 LLM 컴포넌트 | [Product Catalog Query Planner](agents/product-catalog-query-planner.md) | `agent/product/catalog_query.py` |
| 결정론적 검색 컴포넌트 | [Search Service](components/search-service.md) | `agent/search/` |
| 검색·생성 도구 | [Product 상품 비교 도구](components/product-comparison.md) | `agent/product/`의 비교 검색·HCX 생성 |
| 결정론적 계산 컴포넌트 | [Calculation Service](components/calculation-service.md) | `rules/` |

Search Service는 현재 LLM Agent가 아니다. 규칙 기반 Router와 Python 검증으로 검색 계획과
결과를 만든다. Product Catalog Query Planner는 독립 Domain Agent가 아니라 Product Agent의
`lookup_product_codes` Tool 호출마다 계획 하나를 만드는 제한된 LLM 컴포넌트다.
Python은 응답 형식과 카탈로그 선택의 실행 가능 여부를 확인하며, 이름과 코드의 의미 대응은
모델이 판단한다. 실행할 수 없는 카탈로그 선택은 Product에 오류로 전달하고 Product가
`retry_hint`를 넣어 최대 한 번 재조회할 수 있다. Planner 내부의 자동 코드 교정은 하지 않는다.
`compare_products`는 Product가 작성한 자유 비교 쿼리로 상품별 문서를 검색한 뒤 별도 HCX가
답변을 완료하는 도구다. 비교 내용을 고정 항목으로 분류하거나 항목 수를 제한하지 않는다.

`drafts/`는 구현 전 제안을 리뷰하는 공간이다. 구현에 반영된 Product 상품 비교 초안은
위의 현재 스펙으로 이동했으며, 이전 경로에는 이동 안내를 남긴다.

[Product 비교 작성 입력 재구성](drafts/product-comparison-model-context.md)은
[도구의 비교 답변 소유권 결정](../decisions/20260906-product-comparison-answer-ownership.md)으로
대체된 초안이며 당시 제안의 핵심과 대체 이유를 요약해 보존한다.

## 공통 Agent 계약

Main Supervisor는 사용자 질문을 하나의 판단 목표인 `objective`로 나누고 Domain Agent를
Tool로 호출한다. 모든 Domain Agent는 다음 계약을 공유한다.

```text
DomainRequest { question, objective }
    -> DomainResult {
         domain,
         execution_status,
         decision?,
         evidence,
         calculations,
         warnings,
         catalog_result?,
         comparison_answer?,
         error?
       }
```

- `execution_status`: `completed`, `failed`, `timeout`
- `decision.status`: `determined`, `conditional`, `undetermined`, `not_applicable`
- `completed`에는 `decision`이 필요하고 `error`를 포함하지 않는다.
- `failed`와 `timeout`에는 정제된 `error`가 필요하며 `decision`, 근거와 계산을 포함하지 않는다.
- 일반 결과의 `determined`와 `not_applicable`에는 누락 조건을 포함하지 않는다.
- 일반 결과의 `conditional`과 `undetermined`에는 하나 이상의 구체적인 누락 조건이 필요하다.
  Product가 준비한 `comparison_answer`에는 이 판단 상태·조건 조합 검사를 적용하지 않는다.
- 확정 수치는 Python 계산 결과만 사용할 수 있다. 공용 Calculation Service의 active 함수와
  Agent 연결 상태는 [Calculation Service 스펙](components/calculation-service.md)에 명시한다.
- 검색 결과 전체가 아니라 결론에 실제 사용한 청크만 `evidence`로 제출한다.
- `comparison_answer`는 비교 도구의 완성 답변이나 Python의 식별·근거 부족 안내다.
  완료된 Product 결과에만 허용하며 판단·선택 근거·조건·경고와 함께 보존한다.
  `catalog_result`와 함께 넣지 않는다. 답변 내용·인용 의미를 자동 검증하거나 Product가
  재작성하지 않는다. 별도 셀 결과나 비교 완성도 계약은 사용하지 않는다.

실행 가능한 타입과 검증의 최종 기준은
`pension_agent/agent/contracts/domain.py`이며, 스펙과 코드가 다르면 배포 전에 둘을 같은
변경에서 일치시켜야 한다.

## 공통 실행 예산

기본값은 프로세스 단위이며 상위 deadline을 하위 호출이 연장하지 않는다.

| 경계 | 기본값 |
|---|---:|
| 전체 `/answer` deadline | 180초 |
| 활성 `/answer` | 4개 |
| 대기 `/answer` | 64개 |
| 동시 HCX 호출 | 4개 |
| 동시 embedding 호출 | 4개 |
| 동시 Qdrant 호출 | 4개 |
| Domain Agent deadline | 75초 |
| Domain별 동시 실행 | 3개 |
| Search Service deadline | 45초 |
| Search Service 동시 실행 | 4개 |
| Product 비교 검색 / 독립 생성 예약 | 최대 30초 / 30초 |

## 변경 확인

Agent 스펙 변경 시 최소한 다음을 확인한다.

1. Agent 프롬프트와 Tool 설명·스키마가 스펙과 일치한다.
2. `DomainResult`와 API 5개 필드 계약 테스트가 통과한다.
3. Agent graph를 바꿨다면 `make agent-graph`로 생성물을 갱신한다.
4. 라우팅이나 답변 품질을 바꿨다면 관련 평가 질문과 기대 결과를 함께 추가한다.
5. 모델, 호출 수, timeout 또는 동시성 변경은 config와 결정 기록을 함께 갱신한다.
