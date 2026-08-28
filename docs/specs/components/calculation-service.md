# Calculation Service 스펙

## 목적과 책임

Calculation Service는 원문 대조를 마친 소수의 계산 규칙을 결정론적 Python 함수로
실행한다. LLM, 검색, 문서 파서와 Agent adapter를 포함하지 않는다.

```text
CalculationRequest { calculator_id, inputs }
  -> CALCULATORS에서 명시적 함수 조회
  -> 계산기별 Pydantic 입력 검증
  -> Python 함수 실행
  -> CalculationResult
```

현재 확장 지점은 `pension_agent.rules.calculators.CALCULATORS` 딕셔너리 하나다. 동적 등록,
lifecycle, 다중 버전 선택, 적용 기간과 계산 permission은 구현하지 않는다.

## 요청과 결과

`CalculationRequest`는 다음 필드만 허용한다.

| 필드 | 설명 |
|---|---|
| `calculator_id` | `CALCULATORS`의 snake_case 계산기 ID |
| `inputs` | 계산기별 Pydantic 입력 모델에 전달할 값 |

`CalculationResult`는 다음 내용을 반환한다.

- 계산기 ID
- Pydantic이 정규화한 입력
- 출력 키별 값과 단위
- 계산 결과 사용 시 확인해야 할 warning

금액과 비율은 `Decimal`로 계산하고 JSON에서는 문자열로 직렬화한다. 계산 출처는 현재
결과와 Agent의 `evidence`에 포함하지 않는다. PDF와 formula catalog는 오프라인 산식 검증
자료로만 관리한다.

## 등록된 계산기

| 계산기 ID | 산식·규칙 | 검증 문서 |
|---|---|---|
| `pension_withdrawal_limit` | 평가액 ÷ (11 - 수령연차) × 120%, 1~10년차 | `doc2.pdf` 1쪽 |
| `pension_tax_credit` | 일반 납입 한도(연금저축 600만원·통합 900만원), 소득 경계 16.5%/13.2%, ISA 추가공제(전환액 10%·동일 만기 누적 300만원) | `doc41.docx` 1쪽, `doc6.docx` 3쪽 |
| `fund_standard_price` | (자산총액 - 부채총액) ÷ 총좌수 × 1,000, 소수 셋째 자리 반올림 | `R2_KR510902511M.pdf` 24쪽 |
| `fund_var_risk` | `abs(일간 2.5퍼센타일 손실률) × √250` 후 6단계 상한표 | `R2_KR5160420009.pdf` 20쪽 |

검증 문서 정보는 개발 기록이며 런타임 결과에 직렬화하지 않는다. 문서에 없는 표시
자릿수나 최종 지급 단위 반올림은 임의로 적용하지 않고 warning에 남긴다.

### `pension_tax_credit` 계약

**필수 입력**: `pension_savings_net_contribution_krw`(연금저축 순납입액),
`retirement_pension_net_contribution_krw`(퇴직연금 순납입액).

**선택 입력**: `pension_savings_isa_transfer_krw`, `retirement_pension_isa_transfer_krw`
(ISA 만기자금 전환액), `prior_same_maturity_isa_extra_eligible_contribution_used_krw`
(같은 만기자금의 전년도 추가 공제대상액 사용분, 0~300만원), `income_basis`(`salary` 또는
`comprehensive_income`), `income_amount_krw`(소득금액), `remaining_tax_before_pension_credit_krw`
(연금계좌 세액공제 적용 직전 잔여 산출세액).

**생략/0/null 계약**: 선택 입력은 필드 자체를 생략하는 것과 값 `0`을 명시적으로 전달하는
것을 다르게 취급한다. 생략은 "정보 없음"이고 `0`은 "확인된 값이 0"이라는 뜻이다. Pydantic
입력 모델은 명시적 `null` 전달을 거부한다(`reject_explicit_null` 검증기) — 값이 없으면
필드를 아예 포함하지 않아야 한다. ISA 전환액이 하나라도 0보다 크면
`prior_same_maturity_isa_extra_eligible_contribution_used_krw`가 필수이고, ISA 전환액이
모두 0/생략이면 이 필드를 포함할 수 없다. `income_basis`와 `income_amount_krw`는 항상
함께 있거나 함께 생략해야 하며, `remaining_tax_before_pension_credit_krw`는 소득 기준이
있을 때만 허용한다. `CalculationResult.inputs`에는 실제로 전달된(생략되지 않은) 필드만
남는다(`exclude_unset`).

**산식**: 일반 공제대상액은 `min(연금저축 순납입액, 600만원) + 퇴직연금 순납입액`을
`900만원`으로 제한한 값이다. ISA 추가공제는 `ISA 전환액 합 × 10%`와
`max(300만원 - 전년도 사용액, 0)` 중 작은 값이며, 총 공제대상액은 `전체 순납입액`과
`일반 공제대상액 + ISA 추가공제` 중 작은 값으로 다시 제한한다(`isa_extra_limit_krw`는
계산된 ISA 추가한도, `isa_extra_eligible_contribution_krw`는 총액 제한 이후 실제 인정된
값으로 구분해 반환한다). 소득 기준이 있으면 `총급여 5,500만원` 또는 `종합소득금액
4,500만원` 이하일 때 `16.5%`, 초과하면 `13.2%`를 적용한다. 소득 기준이 없으면 두 세율
시나리오(`lower_income_*`/`other_income_*`)를 모두 반환한다.

**이론상 세액과 사용 가능 세액**: `theoretical_credit_krw`(또는 두 시나리오의
`*_theoretical_credit_krw`)는 공제대상액에 세율을 곱한 이론상 수치일 뿐이다.
`remaining_tax_before_pension_credit_krw`가 있을 때만 `usable_credit_krw`
(`min(이론상 세액, 잔여 산출세액)`)를 추가로 반환하며, 이는 실제 환급액이 아니다.

**반올림**: 원 단위 세액의 반올림·절사 규칙은 검증 문서에 없으므로 임의로 적용하지 않고
`CalculationOutput.warnings`에 남긴다(계산 결과가 실제 환급액이 아니라는 warning도 함께
포함).

## 실행 제한과 오류

- 문자열 수식, DSL, `eval`과 동적 모듈 import를 실행하지 않는다.
- 계산 함수는 네트워크, 파일, 현재 시간, 난수와 환경변수를 읽지 않는다.
- `rules`는 `agent`, `retrieval`, `ingest`를 import하지 않는다.

| 오류 | 조건 |
|---|---|
| `CalculatorNotFoundError` | 계산기 ID가 등록되지 않음 |
| `InvalidCalculationInputError` | Pydantic 입력 검증 실패 |
| `CalculationExecutionError` | 검증 후 산술 조건을 만족하지 못함 |

입력 오류는 필드 경로와 Pydantic 오류 코드만 보존하며 원시 입력값을 오류 문자열에 넣지
않는다.

## 계산 함수 추가

1. 원본 PDF 또는 제공 문서에서 산식, 변수, 조건, 단위와 반올림을 직접 대조한다.
2. `extra="forbid"`, `frozen=True`인 Pydantic 입력 모델을 작성한다.
3. 입력 모델 하나를 받아 `CalculationOutput`을 반환하는 순수 Python 함수를 작성한다.
4. `CalculatorDefinition`을 만들고 `CALCULATORS`에 계산기 ID 한 항목을 추가한다.
5. 정상값, 경계값, 잘못된 입력, 반올림과 결정성 테스트를 추가한다.

## Agent 연결 경계

Calculation Service에는 Agent permission 계층을 넣지 않는다. Agent 계층이 계산기별로
명시적인 Tool schema를 만들고 실제 전달한 Tool만 호출할 수 있게 한다.

| 소비자 | 허용 계산기 |
|---|---|
| Tax/Payout Agent | `pension_withdrawal_limit`, `pension_tax_credit` |
| Product Agent | `fund_standard_price`, `fund_var_risk` |
| Policy Agent | 없음 |
| Main Supervisor | 직접 호출 금지 |

Calculation Tool은 완료된 검색 근거가 있어야 실행되고 결과를 Agent state에 직접 누적한다.
각 입력에는 필드명, 단일 값과 단위를 포함한 원문 `source`가 필요하며 Agent adapter가 질문과
검색 청크의 실제 구절인지 확인한 뒤 수치를 정규화한다. 필드 의미가 다르거나 출처가 없거나
여러 수치가 섞인 구절은 실행하지 않는다. 검증된 출처는 `question` 또는 `evidence` origin과
검색 청크 ID로 `CalculationResult.input_sources`에 보존한다.
검색 청크에서 가져온 계산 입력은 해당 청크를 최종 `DomainResult.evidence`에 자동 포함한다.
출처 청크가 최종 evidence에 없으면 공통 계약 검증에 실패한다. `AnswerService`는 계산만 있는
답변을 검증된 Python 결과로 교체하고 복합 답변에는 같은 결과를 결정론적으로 덧붙인다.
일부 계산만 성공한 `conditional`·`undetermined` 결과는 상태와 누락 조건을 유지한다.

## 검증 위치

- `tests/unit/rules/test_calculation_service.py`
- `tests/unit/rules/test_initial_calculators.py`
- `tests/unit/rules/test_pension_tax_credit.py`
- `tests/unit/agent/test_calculation_tools.py`
- `tests/unit/agent/test_domain_agents.py`
- `tests/test_agent_import_boundaries.py`
