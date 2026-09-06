# Product 상품 비교 도구 스펙

- 상태: 구현 계약
- 갱신일: 2026-09-06
- 구현: `pension_agent/agent/product/comparison.py`, `comparison_answer.py`
- 설정: `pension_agent/config/product_comparison.py`, `pension_agent/config/hcx.py`

현재 계약은 [상품 비교 통합 결정](../../decisions/20260906-product-comparison.md)을 따른다.
상품 선택·재조회는 [Catalog Planner](../agents/product-catalog-query-planner.md), 상위 도구
실행은 [Product Agent](../agents/product-agent.md), 검색은 [Search Service](search-service.md)를 따른다.
이 스펙은 실행 계약이며 실제 답변의 정확성을 보증하는 평가 기록이 아니다.

## 책임

| 주체 | 책임 |
|---|---|
| Main Supervisor | 상품 비교를 `analyze_product`에 위임 |
| Product ReAct | 카탈로그 식별 후 자유로운 비교 쿼리를 작성하고 도구 호출 |
| Catalog Planner + Python | 모델이 상품을 선택하고 Python이 조회의 실행 가능 여부 확인 |
| 도구 내부 Python | 같은 쿼리로 상품별 문서 검색, 실행 상태·근거 관리 |
| 도구 내부 HCX | 질문·비교 쿼리·검색 근거를 받아 답변과 사용 근거 선택 |
| AnswerService | 완료된 비교 응답을 다른 Domain 결과와 함께 최종 전달 |

`compare_products`는 검색부터 답안 작성까지 완료한다. 완료 후 Product가 다시 작성하거나
`submit_domain_result`로 비교 셀을 제출하지 않는다. 비교 항목 enum·개수 상한, 셀·coverage,
답변의 의미 검증과 검증 후 재작성, 보완 검색은 두지 않는다.

## 도구 입력

```json
{
  "product_codes": ["KR5153420063", "KR5153420079"],
  "comparison_query": "두 상품의 투자대상과 원금손실 가능성을 비교해 설명한다."
}
```

| 입력 | 계약 |
|---|---|
| `product_codes` | 중복 없는 2~5개 코드, 카탈로그 조회로 확정된 전체 코드와 순서까지 일치 |
| `comparison_query` | Product가 작성하는 비어 있지 않은 문자열. 검색과 답안 생성에 함께 사용 |
| 자동 주입 | 질문 원문, 판단 목표, 전체 대상, 카탈로그 버전, 상위 deadline |

비교 쿼리는 사용자의 목적과 설명할 내용을 자유롭게 표현한다. 미리 정한 항목 목록으로
분류하거나 1~3개로 자르지 않는다. Python은 앞뒤 공백만 정리하고 본문·개행을 유지한다.
파일명·문서 ID·검색 개수·timeout은 모델 입력으로 받지 않는다.

선행 `lookup_product_codes`는 상품 식별만 수행하고 비교 쿼리를 받지 않는다. 최초 호출은
무인자이며, 실행 불가 선택의 재조회에만 선택적 문자열 `retry_hint`를 사용할 수 있다.
Planner는 호출마다 계획 하나를 만들고 명시적인 복수 요청은 2~5개 `targets`로 반환한다.
Python은 자료형·기본 계약·카탈로그 코드 존재 등을 확인한다. 이름·코드의 의미 대응은
모델이 판단하므로 카탈로그에 존재하는 다른 상품을 잘못 선택한 경우도 통과할 수 있다.

실행할 수 없는 코드 등 카탈로그 선택 오류는 정제된 오류와 `submitted_query`로 Product에
돌려준다. Product는 이를 보고 최대 한 번 재조회할 수 있다. Planner 내부 자동 교정은
없으며 질문·판단 목표와 기존 deadline을 유지한다. provider 호출·응답 형식 오류에는
재조회를 적용하지 않는다. 두 번째 조회도 실패하면 종료한다.

서로 다른 확정 코드가 2개 이상일 때 비교를 실행한다. 미식별 대상은 전체 대상에 남겨
작성기에 전달하며 같은 코드의 반복 표현은 검색을 한 번만 수행한다. 0~1개이면 검색과
작성 모델을 호출하지 않고, Python이 대상과 식별 부족 이유를 `comparison_answer`로 반환한다.

## 실행 흐름

```text
Main → analyze_product
  → Product: lookup_product_codes()
      → Catalog Planner 계획 1개 → Python 카탈로그 조회
      → 실행 불가 선택이면 Product가 retry_hint로 최대 1회 재조회
  → Product: compare_products(확정 코드 전체, comparison_query)
      → 같은 comparison_query로 상품별 문서 검색을 한 번씩 병렬 실행
      → 원문 질문·목표·비교 쿼리·상품별 근거로 독립 모델 입력 구성
      → HCX가 답변과 사용한 청크 ID를 한 번 제출
  → Product 종료 → Main → AnswerService → API
```

비교 대상 식별 후 Product에는 `compare_products`만 실행하도록 안내한다. 이전 도구 메시지를
읽기 위한 schema가 남아 있어도 순서·횟수 제한이 재실행을 막는다. 단일 상품·카탈로그 조회의
검색·계산·제출 경로는 유지한다.

## 상품별 검색과 생성 입력

모든 상품에서 검색 문장은 동일한 `comparison_query`다. Python이 상품명이나 고정 검색어를
덧붙이지 않으며 상품별 `source_file_name` 범위만 달리한다. `Permission.PRODUCT`와 기존
Search Service·embedding·Qdrant의 공통 제한을 사용한다.

상품별 검색 시도와 확보한 근거, 전체 대상·비교 쿼리·검색 상태·제한을 보존한다. 각 상품은
한 번 검색하고 보완 검색은 수행하지 않는다. 검색 실패나 빈 결과를 다른 상품 근거로
대체하지 않는다.

독립 작성 입력은 전용 system prompt와 다음 정보를 담은 요청 메시지 하나다.

- 질문 원문과 판단 목표, `comparison_query`
- 카탈로그 버전과 전체 대상: 공식명·코드·모델이 해석한 표현·미식별 상태
- 상품별 검색 상태·오류·근거 ID와 실행 제한
- 고유 청크의 ID·파일명·제목·위치·전체 본문

이전 Product 대화, 전체 카탈로그와 과거 비교 답변은 넘기지 않는다. 동일 청크 ID는 처음
확보한 원문을 한 번 전달하고 상품별 참조 관계를 유지한다. 고유 원문 요약·문자열 자르기·
추가 입력 토큰 상한은 적용하지 않는다.

## 실패와 부분 결과

| 상황 | 처리 |
|---|---|
| 확정된 서로 다른 코드가 0~1개 | 검색·생성 없이 대상과 식별 부족 이유를 담은 비교 안내 |
| 모든 상품에서 근거 확보 | 확보 근거로 작성 모델 호출 |
| 일부 상품에서 근거 확보 | 근거와 실패·미식별 상태를 함께 작성 모델에 전달 |
| 완료된 검색은 있으나 근거 없음 | 새 생성 없이 근거 부족 안내와 `undetermined` 결과 |
| 모든 검색이 timeout | Product `timeout`, 정제된 오류 |
| 완료된 검색 없이 실패 포함 | Product `failed`, 정제된 오류 |
| 비교 도구 입력 계약 위반 | 검색 전 실패, 입력을 임의 변경하지 않음 |
| 작성 모델의 응답 형식 오류 | 내용 교정 없이 실패 |

Python의 미완료 안내도 `comparison_answer`와 `decision.conclusion`에 담는다. 식별 부족은
대상과 이유를 간단히 설명하며 셀이나 비교 완성도 값을 만들지 않는다. 부모 timeout·취소는
전파하며, 부분 근거는 부모 마감 전에 결과를 완료한 경우에 보존한다.

## 생성 결과와 전달

작성 모델은 `submit_comparison_answer`를 한 번 호출한다.

| 반환 필드 | 의미 |
|---|---|
| `answer` | 사용자에게 전달할 한국어 비교 답안 |
| `status` | `determined`, `conditional`, `undetermined`, `not_applicable` |
| `missing_conditions` | 판단에 필요한 정보와 설명하지 못한 범위 |
| `warnings` | 적용 조건과 제한 |
| `evidence_chunk_ids` | 답변에 사용한 검색 청크 ID |

Python은 자료형과 기본 계약을 파싱하고 선택 ID를 실제 청크에 연결한다. 존재하지 않는
ID는 제외하고 중복을 제거하며 그 이유로 답변을 거절하거나 다시 쓰지 않는다. 완성 답변은
`DomainResult.comparison_answer`와 `decision.conclusion`에 같은 본문으로 보존한다.
선택 근거·조건·경고도 함께 반환하며 계산 결과는 생성하지 않는다.

모델은 질문에 필요한 사실만 설명하고 상품·모펀드/자펀드·클래스·시점·예외를 구분하도록
지시받는다. 본문 설명에 직접 출처를 붙이고 실제 사용한 청크만 선택하도록 안내한다.
이름별 예외나 인용 개수 상한은 없으며, 요청 충족·인용 의미·추천의 적절성을 자동 판정하는
검증기도 없다. 프롬프트 준수와 답변의 정확성은 별도 평가 대상이다.

Main에는 `comparison_answer_ready=true`와 decision을 전달하고 원문 청크는 별도 state에
보존한다. AnswerService는 준비된 비교 본문·조건·경고를 유지하며 Main의 새 비교 문장은
채택하지 않는다. 청크별 출처 목록을 답변 끝에 강제로 추가하지 않는다. 다른 Domain의
부분 실패·계산·숫자 처리 계약은 [Main Supervisor](../agents/main-supervisor.md)를 따른다.

API는 `question_id`, `question`, `retrieved_context`, `think_trace`, `answer`의 정확한
5필드를 유지한다. 비교의 `retrieved_context`에는 실제 검색 결과에 있는 선택 근거만
포함하며, 모델이 그 근거를 실제 문장에 올바르게 사용했다는 보장은 아니다.

## 실행 예산과 확인

| 경계 | 기본값 |
|---|---|
| 전체 비교 대상 | 최대 5개, 미식별·동일 코드 반복 표현 포함 |
| 카탈로그 조회 | 기본 1회, 실행 불가 선택의 재조회에만 1회 추가 |
| `compare_products` | 요청당 1회, 확정 상품마다 검색 1회 |
| 비교 검색 마감 | `min(진입 시각 + 30초, Domain deadline - 30초)` |
| Product ReAct | 기존 최대 5회, 비교 답변 이후 재호출 없음 |
| 독립 작성 모델 | HCX-007, Thinking `none`, temperature `0.1`, 최대 출력 4096토큰 |
| 작성 호출 | 논리적 1회, provider timeout 30초·SDK retry 0회 |
| 공통 429 재시도 | 같은 deadline 안에서 최대 1회 추가 물리 호출 |
| Domain / API deadline | 75초 / 180초, 기존 동시성 공유 |

검색을 위해 예약한 시간이나 작성에 남긴 30초는 완료 보장이 아니다. 대기·검색·인프라
재시도는 같은 마감을 사용하며 부모 deadline을 연장하지 않는다.

테스트는 같은 비교 쿼리와 서로 다른 문서 범위, 부분 실패·취소, 독립 생성과 최종 본문·
근거 보존을 확인한다. 실제 HCX 평가는 상품 선택, 검색 적합성, 설명의 사실·조건·인용,
완료율·지연을 나누어 확인한다. 과거 항목·셀 계약의 실험 결과를 새 계약의 성공 근거로
사용하지 않는다. 개인 질문·추적 링크·인증값은 [개인 추적 정책](../../operations/langsmith-tracing.md)에
따라 공용 문서와 PR에 포함하지 않는다.
