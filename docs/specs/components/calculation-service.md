# Calculation Service 스펙

## 목적과 책임

Calculation Service는 원문 검증을 통과한 계산 규칙을 결정론적 Python 함수로 실행한다.
LLM Agent가 아니며 모델, 검색, 파싱 라이브러리를 호출하지 않는다. 구현은
`pension_agent/rules/`가 소유하고 특정 Domain Agent에 종속되지 않는다.

```text
CalculationRequest
  -> Calculator Registry
  -> active 버전·적용일·소비자 권한 확인
  -> Pydantic 입력 검증
  -> 등록된 Python callable 실행
  -> CalculationResult
```

추출된 계산식 카탈로그는 오프라인 후보 선별 자료다. 제품 런타임은 Docling bundle,
formula catalog 또는 HTML 보고서를 읽지 않는다.

## 요청과 결과

`CalculationRequest`는 다음 필드를 허용한다.

| 필드 | 필수 | 설명 |
|---|---|---|
| `calculator_id` | 예 | Registry의 snake_case 계산기 ID |
| `inputs` | 예 | 계산기별 Pydantic 입력 모델에 전달할 값 |
| `version` | 아니요 | `major.minor.patch` 규칙 버전 |
| `effective_on` | 아니요 | 적용 기간이 여러 개인 규칙의 기준일 |
| `consumer` | 아니요 | adapter 연결 후 allowlist 검증에 사용할 소비자 ID |

버전을 생략했을 때 active 버전이 하나면 그 버전을 사용한다. active 버전이 여러 개면
`version` 또는 하나로 결정할 수 있는 `effective_on`이 필요하다. 명시한 버전은 active여야
한다.

`CalculationResult`는 다음 내용을 보존한다.

- 계산기 ID·버전·표시 이름과 도메인 태그
- Pydantic이 정규화한 입력
- 출력 키별 값과 단위
- 규칙 family ID와 전체 원문 provenance
- 계산 결과 사용 시 확인해야 할 warning

`Decimal`은 JSON에서 문자열로 직렬화한다. 금액·세율 계산에 binary `float`를 사용하지
않는다.

## 규칙 lifecycle

| 상태 | 의미 | 런타임 실행 |
|---|---|---|
| `candidate` | 자동 추출 후보 | 금지 |
| `draft` | 입력·출력과 산식 정규화 중 | 금지 |
| `reviewed` | 원문 대조 완료, 활성화 전 | 금지 |
| `active` | 검증된 출처와 함께 실행 승인 | 허용 |
| `retired` | 다른 버전으로 대체 | 금지 |
| `blocked` | 상수·경계·단위·반올림 등을 확정하지 못함 | 금지 |

active 메타데이터에는 하나 이상의 `RuleSource`가 필요하다. 출처는 family/candidate ID,
파일명, SHA-256, 페이지·section 또는 locator, Drive ID, 추출 방식과 parser profile을
보존한다.

## Registry와 실행 제한

- `CalculatorDefinition`은 메타데이터, Pydantic 입력 모델과 Python callable을 묶는다.
- 같은 `(calculator_id, version)`은 한 번만 등록할 수 있다.
- 문자열 수식, DSL, `eval`과 동적 모듈 import를 실행하지 않는다.
- `allowed_consumers`를 설정한 계산기는 요청에 `consumer`가 있을 때 allowlist를 검증한다.
- 어떤 Agent가 어떤 계산기를 소비할지는 이 컴포넌트가 아니라 후속 adapter 스펙이
  결정한다.
- `rules`는 `agent`, `retrieval`, `ingest`를 import하지 않는다.

## 오류 계약

| 오류 | 조건 |
|---|---|
| `CalculatorNotFoundError` | 계산기 ID 또는 버전이 등록되지 않음 |
| `CalculatorNotActiveError` | active이거나 적용일에 맞는 규칙이 없음 |
| `CalculatorVersionRequiredError` | active 후보가 여러 개라 하나로 결정할 수 없음 |
| `CalculatorConsumerNotAllowedError` | 제공된 소비자가 allowlist에 없음 |
| `InvalidCalculationInputError` | Pydantic 입력 검증 실패 |
| `CalculationExecutionError` | 검증 후 산술 조건을 만족하지 못함 |

입력 오류는 필드 경로와 Pydantic 오류 코드만 보존하며 원시 입력값을 오류 문자열에 넣지
않는다.

## 초기 active 계산기

| 계산기 ID | 도메인 태그 | 산식·규칙 | 주요 출처 |
|---|---|---|---|
| `pension_withdrawal_limit` | `pension`, `withdrawal_limit` | 평가액 ÷ (11 - 수령연차) × 120%, 1~10년차 | `doc2.pdf` 1쪽, family `b7dfcdf45499a9f10327` |
| `fund_standard_price` | `product`, `fund_price` | (자산총액 - 부채총액) ÷ 총좌수 × 1,000, 소수 셋째 자리 반올림 | `R2_KR510902511M.pdf` 24쪽, family `b90977046022dd5ed540` |
| `fund_var_risk` | `product`, `risk` | `abs(일간 2.5퍼센타일 손실률) × √250` 후 6단계 상한표 | `R2_KR5160420009.pdf` 20쪽, families `702a66c07e5c2e2d94cd`, `a3ab54a1fcb7fd5cbf6f` |

표시 자릿수나 최종 지급 단위의 반올림이 출처에 없으면 계산 결과 warning에 명시한다.
기준가격 계산은 원문에 있는 원 미만 셋째 자리 반올림을 `ROUND_HALF_UP`으로 적용한다.

## 계산 함수 추가 가이드

### 1. 후보와 원문 검증

1. 카탈로그에서 함수화 후보를 찾는다.
2. family의 모든 occurrence를 동일 규칙으로 가정하지 않는다.
3. 원본 PDF 또는 제공 문서에서 산식, 변수 의미, 적용 기간, 조건표, 단위와 반올림을 직접
   대조한다.
4. 확인할 수 없는 요소가 있으면 `blocked`로 남기고 active 함수로 등록하지 않는다.

### 2. 계약 작성

1. 하나의 책임을 나타내는 `calculator_id`와 semantic version을 정한다.
2. `extra="forbid"`, `frozen=True`인 Pydantic 입력 모델을 작성한다.
3. 금액과 비율에 `Decimal` 범위 제약을 설정한다.
4. 출력 키와 단위를 명시하고 필요한 warning을 작성한다.
5. 각 독립 산식·조건표의 `RuleSource`를 모두 추가한다.

### 3. 함수와 Registry 등록

1. 함수는 입력 모델 하나를 받아 `CalculationPayload`만 반환한다.
2. 전역 decimal context에 의존하지 않고 `localcontext()`에서 precision을 고정한다.
3. 네트워크, 파일, 현재 시간, 난수와 환경변수를 읽지 않는다.
4. `CalculatorDefinition`을 만들고 `INITIAL_CALCULATORS`에 명시적으로 추가한다.
5. Agent 또는 API 모듈을 import하지 않는다.

### 4. 검증

- 정상값과 문서 예시값
- 0, 음수와 최소·최대 경계
- 조건표의 각 경계와 바로 위·아래 값
- 0으로 나누기와 입력 누락·추가 필드
- 반올림 절반값과 단위
- 같은 요청의 결정성
- 계산기 ID·버전·상태·출처 누락
- JSON에서 Decimal 문자열 직렬화

## Agent 연결 경계

현재 어떤 Agent도 Calculation Service를 호출하지 않는다. Tax/Payout, Product와 Policy
adapter는 실제 평가 질문, 필요한 입력과 접근 권한을 확인한 후 별도 이슈에서 연결한다.
각 adapter는 다음을 별도로 명세해야 한다.

1. 허용 계산기 allowlist
2. 사용자 질문에서 신뢰할 수 있는 입력을 만드는 방법
3. 누락 조건과 적용 불가 처리
4. DomainResult 또는 전용 결과 계약으로의 직렬화
5. LLM이 Python 결과의 확정 숫자를 변경하지 못하게 하는 최종 응답 안정화

Main Supervisor에는 범용 계산 실행 권한을 주지 않는다.

## 검증 위치

- `tests/unit/rules/test_calculation_service.py`
- `tests/unit/rules/test_initial_calculators.py`
- `tests/test_agent_import_boundaries.py`
