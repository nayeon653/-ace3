# Calculation Service 스펙

## 목적과 책임

Calculation Service는 원문 대조를 마친 계산 규칙을 결정론적 Python 함수로 실행한다.
LLM, 검색, 문서 파서, 상품·세법 조건 판단과 Agent permission은 포함하지 않는다.

```text
CalculationRequest { calculator_id, inputs }
  -> CALCULATORS에서 명시적 함수 조회
  -> 계산기별 Pydantic 입력 검증
  -> 순수 Python 함수 실행
  -> Rules CalculationResult
  -> Agent adapter가 input_sources를 결합
  -> Agent CalculationResult
```

확장 지점은 `pension_agent.rules.calculators.CALCULATORS` 딕셔너리 하나다. 동적 등록,
문자열 수식, 규칙 DSL, 다중 버전 선택과 런타임 문서 조회는 도입하지 않는다.

## 계약 상태

이 문서는 현재 구현과 다음 구현 범위를 함께 관리한다. 상태의 의미는 다음과 같다.

| 상태 | 의미 |
|---|---|
| `active` | `CALCULATORS`에 등록되고 Agent Tool로 연결되어 현재 호출할 수 있음 |
| `planned` | 원문으로 입력·산식·경계·출처를 확정했지만 아직 등록하거나 호출할 수 없음 |

구현 PR은 계산기와 테스트, Agent Tool과 허용 목록을 함께 추가한 뒤 해당 항목을
`planned`에서 `active`로 옮긴다. 구현 전까지 각 Agent 스펙과 Tool 허용 목록은 현재의
`active` 집합만 설명한다. 스펙에 `planned`로 적혔다는 이유로 Agent가 임의 계산하거나
등록되지 않은 ID를 호출해서는 안 된다.

## 공통 요청과 결과 계약

### 요청

`CalculationRequest`는 다음 필드만 허용한다.

| 필드 | 설명 |
|---|---|
| `calculator_id` | `CALCULATORS`의 snake_case 계산기 ID |
| `inputs` | 계산기별 `extra="forbid"`, `frozen=True` Pydantic 입력 모델에 전달할 값 |

금액·비율·좌수는 이진 부동소수점으로 계산하지 않고 `Decimal`을 사용한다. 날짜 입력은
`YYYY-MM-DD` 달력 날짜, 조건 입력은 계산기별 enum 또는 boolean으로 정규화한다. 선택 입력을
보내지 않은 경우 정규화된 `inputs`와 `input_sources` 양쪽에서 그 키를 생략한다. 구현은
`exclude_unset=True`, `exclude_none=True`로 이 계약을 지키며 명시적인 입력 `null`은
거부한다. `0`과 `false`는 실제 입력값으로 보존하고, `null`은 적용할 수 없는 결과를
표현하는 출력에서만 사용한다.

### Rules 결과

`pension_agent.rules`의 `CalculationResult`는 다음 값만 반환한다.

- `calculator_id`
- Pydantic이 정규화한 `inputs`
- 계산기의 `outputs`
- 출력 키별 `units`
- 계산 결과를 해석할 때 필요한 `warnings`

`Decimal`은 JSON에서 문자열로 직렬화한다. Rules 결과는 출처 파일, 검색 청크와
`input_sources`를 포함하지 않는다.

### Agent 결과와 입력 출처

Agent adapter의 `CalculationResult`는 Rules 결과에 아래 필드를 추가한다.

```text
input_sources[input_field] = {
  origin: "question" | "evidence",
  text: 원문 구절,
  chunk_id: evidence일 때 검색 청크 ID, question일 때 null
}
```

정규화된 `inputs`와 `input_sources`의 키는 정확히 같아야 한다. 검색 청크에서 가져온 입력은
그 청크가 최종 `DomainResult.evidence`에도 포함되어야 한다. 계산기는 완료된 검색 근거가
있을 때만 실행하며, 입력 출처는 질문 또는 검색 청크의 실제 부분 문자열이어야 한다.

현재 숫자 입력 검증은 계산기별 필드 의미와 단위, 정규화된 목표 숫자를 확인한다. `planned`
계산기를 연결할 때는 다음 최소 확장을 함께 구현한다.

- 숫자·날짜·enum·boolean 각각에 필드 의미를 식별하는 label을 정의한다.
- 목표 입력값은 label·단위와의 결합으로 다른 숫자 후보와 모호하지 않게 식별되어야 한다.
  동일한 값이 표와 본문에 반복되었다는 이유만으로 거부하지 않는다.
- 기간이나 한도 같은 보조 숫자가 같은 구절에 있어도 목표 값과 label·단위가 유일하면
  허용한다. 예를 들어 `3년 미만 0.15% 이내`에서 기간과 수수료율을 구분한다.
- `수익률변동성`이라는 표현만으로는 표준편차인지 VaR인지 구분할 수 없으므로
  `fund_reported_var_risk` 입력으로 인정하지 않는다.
- 계산기 내부 상수와 고정 세율은 Tool 입력이 아니므로 호출별 `input_sources`를 요구하지
  않는다.
- 이전 계산의 결과를 새 Tool 입력 출처로 사용하지 않는다. 여러 규칙을 합칠 필요가 있으면
  하나의 명시적 합성 계산기가 내부에서 순수 함수를 직접 조합한다.

계산 출처 파일은 런타임 결과에 넣지 않는다. 원문 파일과 locator의 유일한 스펙 매핑은 이
문서의 [출처 매핑](#출처-매핑)에서만 관리한다.

## `active` 계산기

현재 등록 집합은 아래 세 개와 정확히 일치한다.

| 계산기 ID | 소비자 | 구현 상태 |
|---|---|---|
| `pension_withdrawal_limit` | Tax/Payout Agent | `active` |
| `fund_standard_price` | Product Agent | `active` |
| `fund_var_risk` | Product Agent | `active` |

### `pension_withdrawal_limit`

| 구분 | 계약 |
|---|---|
| 입력 | `account_valuation_krw >= 0`, `pension_year` 1~10 정수 |
| 산식 | `account_valuation_krw / (11 - pension_year) * 1.2` |
| 출력 | `withdrawal_limit` (`KRW`) |
| 반올림 | 적용하지 않음 |
| warning | 최종 지급 단위의 반올림·절사 규칙이 원문에 없음 |

11년차 이후 계약은 [#116](https://github.com/nayeon653/-ace3/issues/116)의 `planned`
확장으로 별도 정의한다.

### `fund_standard_price`

| 구분 | 계약 |
|---|---|
| 입력 | `total_assets_krw >= 0`, `total_liabilities_krw >= 0`, `total_units > 0` |
| 추가 검증 | `total_liabilities_krw <= total_assets_krw` |
| 산식 | `(total_assets_krw - total_liabilities_krw) / total_units * 1000` |
| 출력 | `standard_price_per_1000_units` (`KRW/1,000 units`) |
| 반올림 | 0.01원 단위 `ROUND_HALF_UP` |

### `fund_var_risk`

| 구분 | 계약 |
|---|---|
| 입력 | `daily_loss_percentile_percent` -100~100% |
| 산식 | `abs(daily_loss_percentile_percent) * sqrt(250)` |
| 출력 | `annualized_var_percent`, `risk_grade`, `risk_label` |
| 반올림 | 적용하지 않음 |
| warning | 표시 자릿수·반올림 규칙이 원문에 없음 |

연환산 97.5% VaR의 등급 경계는 다음과 같다.

| 연환산 VaR | 등급 | label |
|---|---:|---|
| `> 50%` | 1 | 매우 높은 위험 |
| `> 30%, <= 50%` | 2 | 높은 위험 |
| `> 20%, <= 30%` | 3 | 다소 높은 위험 |
| `> 10%, <= 20%` | 4 | 보통 위험 |
| `> 1%, <= 10%` | 5 | 낮은 위험 |
| `0% <= 값 <= 1%` | 6 | 매우 낮은 위험 |

## `planned` 계산기 목록

| 이슈 | 계산기 ID | 예정 소비자 |
|---|---|---|
| [#112](https://github.com/nayeon653/-ace3/issues/112) | `pension_tax_credit` | Tax/Payout Agent |
| [#113](https://github.com/nayeon653/-ace3/issues/113) | `pension_income_tax`, `non_pension_withdrawal_tax` | Tax/Payout Agent |
| [#114](https://github.com/nayeon653/-ace3/issues/114) | `deferred_retirement_withdrawal_tax` | Tax/Payout Agent |
| [#115](https://github.com/nayeon653/-ace3/issues/115) | `pension_withdrawal_allocation`, `pension_withdrawal_tax_breakdown` | Tax/Payout Agent |
| [#116](https://github.com/nayeon653/-ace3/issues/116) | `pension_withdrawal_limit` 확장, `pension_annual_limit_installment`, `pension_period_installment`, `pension_unit_installment` | Tax/Payout Agent |
| [#117](https://github.com/nayeon653/-ace3/issues/117) | `dc_medical_withdrawal_threshold` | Policy Agent |
| [#117](https://github.com/nayeon653/-ace3/issues/117) | `medical_care_withdrawal_tax_limit`, `medical_care_withdrawal_tax_breakdown` | Tax/Payout Agent |
| [#118](https://github.com/nayeon653/-ace3/issues/118) | `db_retirement_benefit`, `dc_minimum_contribution`, `dc_retirement_benefit`, `db_to_dc_transfer_amount` | Tax/Payout Agent |
| [#119](https://github.com/nayeon653/-ace3/issues/119) | `executive_retirement_income_limit` | Tax/Payout Agent |
| [#120](https://github.com/nayeon653/-ace3/issues/120) | `isa_pension_transfer_deadline` | Policy Agent |
| [#121](https://github.com/nayeon653/-ace3/issues/121) | `fund_reported_var_risk` | Product Agent |
| [#122](https://github.com/nayeon653/-ace3/issues/122) | `fund_frontend_sales_fee`, `fund_deferred_sales_fee`, `fund_redemption_fee` | Product Agent |

## `planned` 세부 계약

### #112 `pension_tax_credit`

입력은 다음과 같다.

- 선택 `pension_savings_net_contribution_krw >= 0`: ISA 전환액을 포함한 연금저축 순납입액
- 선택 `retirement_pension_net_contribution_krw >= 0`: ISA 전환액을 포함한 IRP·DC 순납입액
- 선택 `pension_savings_isa_transfer_krw >= 0`
- 선택 `retirement_pension_isa_transfer_krw >= 0`
- 선택 `0 <= prior_same_maturity_isa_extra_eligible_contribution_used_krw <= 3_000_000`:
  같은 ISA 만기자금으로 전년도에 이미 사용한 추가 공제대상 납입액
- 선택 쌍 `income_basis = salary | comprehensive_income`, `income_amount_krw >= 0`
- 선택 `remaining_tax_before_pension_credit_krw >= 0`: 연금계좌 세액공제를 적용하기 직전의
  잔여 산출세액

ISA 전환액은 각 계좌의 순납입액을 넘을 수 없다. 전년도 사용액이 없다는 사실이 근거에서
확인되면 위 선택 필드를 생략하고 0으로 계산하며, 사용 여부가 불명확하면 호출하지 않는다.
납입 항목을 생략해 0으로 취급하는 것도 질문이나 근거가 해당 과세연도의 전체 납입
시나리오를 닫은 경우에만 허용하며, 알 수 없는 납입액을 0으로 추정하지 않는다.

```text
regular_base = min(
  9_000_000,
  min(pension_savings_net_contribution_krw, 6_000_000)
    + retirement_pension_net_contribution_krw,
)
isa_transfer = pension_savings_isa_transfer_krw
  + retirement_pension_isa_transfer_krw
prior_used = prior_same_maturity_isa_extra_eligible_contribution_used_krw
  if supplied else 0
isa_remaining = max(
  3_000_000 - prior_used,
  0,
)
isa_extra_limit = min(isa_transfer * 0.10, isa_remaining)
total_net = pension_savings_net_contribution_krw
  + retirement_pension_net_contribution_krw
eligible_contribution = min(total_net, regular_base + isa_extra_limit)
realized_isa_extra = max(eligible_contribution - regular_base, 0)
```

`salary <= 55_000_000` 또는 `comprehensive_income <= 45_000_000`이면 16.5%, 각각의
경계를 초과하면 13.2%다. 소득 쌍이 없으면 `lower_income_rate_percent=16.5`,
`lower_income_theoretical_credit_krw`, `other_income_rate_percent=13.2`,
`other_income_theoretical_credit_krw`를 반환한다.
소득이 있으면 `credit_rate_percent`, `theoretical_credit_krw`를 반환하고, 잔여 산출세액도
있으면 아래 `usable_credit_krw`를 추가한다.

```text
lower_income_theoretical_credit_krw = eligible_contribution * 0.165
other_income_theoretical_credit_krw = eligible_contribution * 0.132
theoretical_credit_krw = eligible_contribution * credit_rate_percent / 100
usable_credit_krw = min(
  theoretical_credit_krw,
  remaining_tax_before_pension_credit_krw,
)
```

공통 출력은 `regular_eligible_contribution_krw=regular_base`,
`isa_extra_limit_krw=isa_extra_limit`,
`isa_extra_eligible_contribution_krw=realized_isa_extra`,
`eligible_contribution_krw=eligible_contribution`이다. 실제 추가 적용액은 반드시
`eligible_contribution_krw - regular_eligible_contribution_krw`와 일치한다. 문서에 없는
반올림은 적용하지 않는다.

### #113 연금수령·연금외수령 세액

#### `pension_income_tax`

공통 입력은 `pension_treatment = ordinary | unavoidable`, 수령일 현재의
`recipient_age >= 0`과 선택 `target_taxable_amount_krw >= 0`다.

- `ordinary`는 `recipient_age >= 55`, `is_lifetime_annuity`와 선택
  `annual_private_pension_taxable_income_krw >= 0`을 받는다. 연간 합계는 현재 계산
  대상액을 포함한 전 금융기관 과세대상 사적연금소득 합계이며, 세액공제를 받지 않은 원금과
  퇴직소득은 제외한다. 대상액과 합계가 함께 있으면
  `target_taxable_amount_krw <= annual_private_pension_taxable_income_krw`여야 한다.
- `unavoidable`은 `is_lifetime_annuity`와 연간 합계를 받지 않는다. 부득이한 사유가
  확인되면 1,500만원 기준과 무관하므로 55세 미만도 허용한다.

`ordinary` 종신연금은 3.3%, 그 외에는 55~69세 5.5%, 70~79세 4.4%, 80세 이상
3.3%를 적용한다. 연간 합계가 없으면 `base_rate_percent`와
`annual_threshold_status=unknown`만 반환하고 세액을 최종값으로 만들지 않는다. 합계가
15,000,000원 이하면 `annual_threshold_status=within`, `filing_choice_required=false`를
반환하고, 대상액이 있으면 `tax_krw = target_taxable_amount_krw * rate`와
`after_tax_krw`를 계산한다.

`ordinary`의 연간 합계가 15,000,000원을 초과하면 종합과세 최종 세액은 계산하지 않는다.
대신 전체 과세대상 사적연금소득에 16.5%를 적용한 `separate_tax_option_tax_krw`,
`annual_threshold_status=exceeded`, `filing_choice_required=true`를 반환한다. 16.5%를
1,500만원 초과분에만 적용해서는 안 된다.

`unavoidable`은 70세 미만 5.5%, 70~79세 4.4%, 80세 이상 3.3%를 적용한다. 대상액이
있으면 `tax_krw`와 `after_tax_krw`를 계산한다. 이 단독 경로의 대상액은 원 근거에서 전액이
저율과세 대상임이 확인된 금액 또는 별도 금액 한도가 없는 부득이한 사유의 금액으로
제한한다. 요양 인출 한도와 세액을 함께 계산할 때는 #117의 합성 계산기를 사용한다. 별도
금액 한도가 없는 재난피해는 이 단독 경로에서 전액을 처리한다. 두 경로 모두 문서에 없는
반올림은 적용하지 않는다.

#### `non_pension_withdrawal_tax`

입력은 세액공제를 받은 원금과 운용수익 중 연금외수령으로 확인된
`taxable_amount_krw >= 0`다.

```text
tax_krw = taxable_amount_krw * 0.165
after_tax_krw = taxable_amount_krw - tax_krw
```

이 계산기는 이연퇴직소득, 나이, 사적연금 연간 합계에 사용하지 않는다. 반올림은 적용하지
않는다.

### #114 `deferred_retirement_withdrawal_tax`

입력은 `receipt_type = pension | non_pension`, 연금수령일 때 필요한
`actual_pension_receipt_year >= 1`과 선택
`allocated_deferred_retirement_tax_krw >= 0`이다. 실제연금수령연차는 실제로 연금을 수령한
연도의 누적 횟수이며, 연금외수령이나 인출이 없던 연도는 누적하지 않는다. 연금수령한도
산식의 연차와도 다르다.

| 수령 구분 | 실제연금수령연차 | 납부 비율 | 감면 비율 |
|---|---:|---:|---:|
| 연금수령 | 1~10년 | 70% | 30% |
| 연금수령 | 11~20년 | 60% | 40% |
| 연금수령 | 21년 이상 | 50% | 50% |
| 연금외수령 | 해당 없음 | 100% | 0% |

```text
tax_payable_krw = allocated_deferred_retirement_tax_krw * payable_ratio
tax_reduction_krw = allocated_deferred_retirement_tax_krw - tax_payable_krw
```

`payable_ratio_percent`와 `reduction_ratio_percent`는 항상 반환한다. 배분세액이 있을 때만
`tax_payable_krw`와 `tax_reduction_krw`를 추가하고, 없으면 두 금액 키를 생략한다.
이연퇴직소득 잔액만으로 배분세액을 임의 추정하지 않으며 문서에 없는 반올림은 적용하지
않는다.

### #115 연금 인출 재원 배분과 세후 내역

#### `pension_withdrawal_allocation`

입력은 `requested_withdrawal_krw`와 다음 세 집계 재원의 현재 잔액이다.

- `tax_free_source_balance_krw`: 과세 결과가 같은 상세 재원 순서 1~5
- `deferred_retirement_source_balance_krw`: 상세 재원 순서 6
- `credited_and_earnings_source_balance_krw`: 세액공제 원금·운용수익인 상세 순서 7~9

모든 값은 0 이상이다. 비과세 재원, 이연퇴직소득, 세액공제 원금·운용수익 순서로 각 단계에
`min(남은 요청액, 해당 잔액)`을 적용한다. 출력은
`tax_free_withdrawal_krw`, `deferred_retirement_withdrawal_krw`,
`credited_and_earnings_withdrawal_krw`와 각 이름의 `_remaining_balance_krw`다. 모든 출력
단위는 `KRW`다. 요청액이 세 잔액 합계를 초과하면 일부 결과를 만들지 않고 입력 오류로
처리한다.

#### `pension_withdrawal_tax_breakdown`

이 계산기는 이전 Tool 결과를 입력받지 않고 위 배분 함수와 #113·#114의 순수 함수를 내부에서
조합한다. 입력은 `pension_withdrawal_allocation`의 네 값과 다음 과세조건이다.

- `pension_treated_withdrawal_krw >= 0`
- `non_pension_treated_withdrawal_krw >= 0`
- 두 수령구분 금액의 합은 `requested_withdrawal_krw`와 같아야 한다.
- 연금수령분이 이연퇴직소득에 배분되면 `actual_pension_receipt_year`
- 연금수령분이 세액공제 원금·운용수익에 배분되면 `recipient_age`,
  `is_lifetime_annuity`와 선택 `annual_private_pension_taxable_income_krw`
- 이연퇴직소득이 각 수령구분에 배분되면 해당 부분의
  `pension_treated_allocated_deferred_retirement_tax_krw`와
  `non_pension_treated_allocated_deferred_retirement_tax_krw`

한도 내 `pension_treated_withdrawal_krw`를 재원 순서의 앞부분에 먼저 배분하고, 이어지는
한도초과액을 `non_pension_treated_withdrawal_krw`로 배분한다. 따라서 한 요청이 연금수령
한도 경계를 가로질러도 두 과세구분을 잃지 않는다. 두 구분 금액과 배분세액이 질문이나 검색
근거에서 각각 확인될 때만 이 합성 계산기를 호출한다. 확인되지 않으면
`pension_withdrawal_allocation`만 실행하고 세액을 추정하지 않는다.

비과세 배분액의 세액은 0원이다. 이연퇴직소득의 두 구분은 #114, 세액공제 원금·운용수익의
연금수령분은 `pension_income_tax`, 연금외수령분은 `non_pension_withdrawal_tax`를 적용한다.
각 재원·수령구분별
`{tax_free|deferred_retirement|credited_and_earnings}_{pension|non_pension}_{withdrawal|tax|after_tax}_krw`와
`current_withdrawal_tax_krw`, `current_withdrawal_after_tax_krw`를 반환한다.

연간 합계가 없거나 1,500만원 초과로 종합과세 선택이 필요하면 현재 인출의 두 합계 출력은
`null`이다. 이때 `annual_private_pension_separate_tax_option_tax_krw`가 있더라도 이는 연간
전체금액의 선택세액이므로 현재 인출 세액 합계에 더하지 않고 warning으로 단위를 구분한다.
부득이한 사유의 저율과세 한도 배분은 이 합성 계산기의 범위에서 제외한다. 실제 비과세 재원
인출액이 0원보다 클 때만 연금수령한도를 소진한다는 warning을 반환한다.

### #116 연금수령한도 확장과 분할지급

#### `pension_withdrawal_limit` 확장

`pension_year >= 1`로 범위를 넓히고 `account_valuation_krw`는 1~10년차에만 필수로 받는다.
1~10년차는 현재 산식을 유지하며 `limit_applies=true`를 추가한다. 11년차 이상은
`limit_applies=false`, `withdrawal_limit=null`을 반환한다. 무제한을 0원이나 임의의 큰
숫자로 표현하지 않는다. 2013년 3월 1일 이전 특례를 포함한 연차 판정은 Agent가 검색 근거로
확정한다.

#### `pension_annual_limit_installment`

입력은 `remaining_annual_limit_krw >= 0`, `remaining_payments_in_year > 0` 정수다.

```text
installment_krw = remaining_annual_limit_krw / remaining_payments_in_year
```

#### `pension_period_installment`

입력은 `current_valuation_krw >= 0`, `remaining_payments > 0` 정수다.

```text
installment_krw = current_valuation_krw / remaining_payments
```

매년 초 새 평가액과 잔여회차로 해당 연도의 동일 지급액을 계산하며, 다음 연도에 다시
산정한다. 이 방식의 상품·계약 적용 가능 여부는 Agent가 근거로 확인한다.

#### `pension_unit_installment`

입력은 `remaining_units >= 0`, `remaining_payments > 0` 정수,
`standard_price_per_1000_units_krw >= 0`다.

```text
installment_krw = remaining_units / remaining_payments
  * standard_price_per_1000_units_krw / 1000
```

세 분할지급 계산기 모두 문서에 없는 좌수·원 단위 반올림은 적용하지 않는다. 기존
개인연금저축 등 적용 대상 판단은 Agent가 수행한다.

### #117 의료비 중도인출과 요양 인출 과세한도

#### `dc_medical_withdrawal_threshold`

DC 계좌에만 호출한다. 입력은
`employment_period = under_one_year | at_least_one_year`, 재직기간에 맞는 임금 근거와
`documented_medical_expense_krw >= 0`다. 의료비는 직전 1년의 실제 지출액과 증빙된
지출 예정액의 합계다.

- 1년 이상은 `previous_year_annual_wage_krw`를 원칙으로 하되, 증빙된
  `preceding_12_month_wage_krw`가 더 낮게 입력되면 그 값을 쓴다.
- 1년 미만은 `monthly_average_wage_krw * 12`를 임금기준으로 쓴다.
- `threshold_krw = wage_basis_krw * 0.125`와
  `documented_medical_expense_krw > threshold_krw`를 판정한다. 정확히 12.5%면
  `threshold_met=false`다.

출력은 `wage_basis_krw`, `threshold_krw`, `threshold_met`이다. DB·IRP에는 이 계산기를
호출하지 않으며, IRP에 12.5% 조건이 없다는 사실만으로 전체 인출 자격을 확정하지 않는다.
다른 중도인출 요건은 Policy Agent가 확인한다. 반올림은 적용하지 않는다.

#### `medical_care_withdrawal_tax_limit`

입력은 0 이상인 `requested_withdrawal_krw`, `documented_medical_expense_krw`,
`documented_care_expense_krw`와 `own_leave_months` 비음수 정수다.

```text
low_rate_limit_krw = 2_000_000
  + documented_medical_expense_krw
  + documented_care_expense_krw
  + own_leave_months * 1_500_000
low_rate_amount_krw = min(requested_withdrawal_krw, low_rate_limit_krw)
excess_amount_krw = requested_withdrawal_krw - low_rate_amount_krw
```

이 산식은 원문에서 확인한 요양 인출에만 사용하며 사유의 성립은 Agent가 먼저 확정한다.
요청액과 한도가 같으면 전액이 한도 내다. 이 계산기는 저율과세 대상액과 초과액만 나누며
세율·세액은 계산하지 않는다. 별도 금액 한도가 없는 재난피해에 이 산식을 적용하지 않는다.

#### `medical_care_withdrawal_tax_breakdown`

이 계산기는 이전 Tool 결과를 입력받지 않고 `medical_care_withdrawal_tax_limit`과
`pension_income_tax`의 순수 함수를 내부에서 조합한다. 입력은
`requested_withdrawal_krw`, `documented_medical_expense_krw`,
`documented_care_expense_krw`, `own_leave_months` 비음수 정수와
`recipient_age >= 0`이다. 요양 사유는 Agent가 원 근거에서 확정한 값이어야 한다.

먼저 저율과세 한도를 계산한 뒤 `low_rate_amount_krw`에만 #113 `unavoidable` 연령세율을
적용한다. 출력은 `low_rate_limit_krw`, `low_rate_amount_krw`,
`low_rate_percent`, `low_rate_tax_krw`, `low_rate_after_tax_krw`,
`excess_amount_krw`다. 금액 단위는 `KRW`, 세율 단위는 `%`다. 초과액은 재원과 수령구분이
없으면 세율·세액을 계산하지 않고 warning으로 남긴다. 요청액 전액에 저율을 적용해서는 안
되며 문서에 없는 반올림은 적용하지 않는다.

```text
low_rate_tax_krw = low_rate_amount_krw * low_rate_percent / 100
low_rate_after_tax_krw = low_rate_amount_krw - low_rate_tax_krw
```

### #118 DB·DC 급여와 전환금액

| 계산기 | 입력 | 산식·출력 |
|---|---|---|
| `db_retirement_benefit` | `wage_total_last_3_months_krw >= 0`, 제외기간을 반영한 `covered_days > 0`, 검증된 `continuous_service_years >= 0` | `daily_average_wage_krw = wage_total / covered_days`; `average_wage_30_days_krw = daily_average_wage_krw * 30`; `retirement_benefit_krw = average_wage_30_days_krw * continuous_service_years` |
| `dc_minimum_contribution` | `annual_wage_total_krw >= 0` | `minimum_employer_contribution_krw = annual_wage_total_krw / 12` |
| `dc_retirement_benefit` | `cumulative_contributions_krw >= 0`, 음수도 가능한 `investment_gain_loss_krw` | `retirement_benefit_krw = cumulative_contributions_krw + investment_gain_loss_krw` |
| `db_to_dc_transfer_amount` | `last_30_day_average_wage_krw >= 0`, `last_annual_wage_total_krw >= 0`, 검증된 `continuous_service_years >= 0` | `transfer_amount_krw = max(last_30_day_average_wage_krw, last_annual_wage_total_krw / 12) * continuous_service_years` |

`dc_minimum_contribution`은 문서의 “연간 임금총액의 1/12 이상” 중 최소액만 반환한다.
제외기간과 근속연수는 계산기가 날짜에서 추정하지 않는다. 네 계산기 모두 금액 출력 단위는
`KRW`이며 문서에 없는 0원 하한이나 반올림을 적용하지 않는다.

### #119 `executive_retirement_income_limit`

입력은 다음 두 기간 쌍 중 적어도 하나와 선택 지급액이다. 각 기간은 급여와 비음수 정수
근무월수를 함께 보내거나 둘 다 생략한다.

- 선택 쌍 `average_annualized_salary_2012_2019_krw >= 0`,
  `service_months_2012_2019 >= 0`: 2019년 12월 31일부터 소급 3년의 총급여 연평균
  환산액과 법정 산정이 끝난 근무월수. 해당 근무기간이 3년 미만이면 실제 기간을 쓴다.
- 선택 쌍 `average_annualized_salary_2020_onward_krw >= 0`,
  `service_months_2020_onward >= 0`: 퇴직일부터 소급 3년의 총급여 연평균 환산액과 법정
  산정이 끝난 2020년 이후 근무월수. 해당 근무기간이 3년 미만이면 실제 기간을 쓴다.
- 선택 `post_2011_limit_subject_payment_krw >= 0`

생략한 기간의 구성액은 0으로 계산하되 해당 기간의 0원 급여 입력과 출처를 만들지 않는다.

```text
limit_2012_2019_krw = average_annualized_salary_2012_2019_krw
  * 1 / 10 * service_months_2012_2019 / 12 * 3
limit_2020_onward_krw = average_annualized_salary_2020_onward_krw
  * 1 / 10 * service_months_2020_onward / 12 * 2
post_2011_total_limit_krw = limit_2012_2019_krw + limit_2020_onward_krw
```

선택 지급액이 있으면 다음 값도 반환한다.

```text
retirement_income_amount_krw = min(
  post_2011_limit_subject_payment_krw,
  post_2011_total_limit_krw,
)
wage_income_excess_krw = max(
  post_2011_limit_subject_payment_krw - post_2011_total_limit_krw,
  0,
)
```

전체 퇴직금이 아니라 반드시 2012년 이후 한도 적용대상 지급액을 입력한다. 2011년 이전
재직분을 포함한 전체 지급액에 `min`을 적용해서는 안 된다. 한 기간의 근무월수 0은 허용하며
문서에 없는 반올림은 적용하지 않는다.

### #120 `isa_pension_transfer_deadline`

입력은 `isa_maturity_date`와 선택 `deposit_processed_date`다.

```text
deadline_date = isa_maturity_date + 60 calendar days
completed_in_time = deposit_processed_date <= deadline_date
```

`deadline_date`는 항상 반환하고 입금처리일이 있을 때만 `completed_in_time`을 추가한다.
입금처리일이 없으면 이 키를 `null`로 만들지 않고 생략한다. 만기일은 세지 않고 다음 날을
1일차로 센다. 신청일이 아니라 연금계좌 입금처리일을 비교한다. 마감일 당일은 적기, 다음
날은 지연이며 주말·공휴일이라고 이월하지 않는다.

### #121 `fund_reported_var_risk`

입력은 문서에 이미 연환산되어 표시된 `annualized_var_percent >= 0`다. 값을 다시
`sqrt(250)`으로 연환산하지 않고 `fund_var_risk`와 같은 경계표를 적용한다. 출력은 입력을
그대로 보존한 `annualized_var_percent` (`%`), `risk_grade`, `risk_label`이다. 상한은 두지
않으며 반올림하지 않는다.

출처 구절에는 `97.5% VaR`, `일간 수익률의 최대손실예상액`처럼 VaR임을 특정하는 문맥과
연환산 값이 함께 있어야 한다. `97.5%`는 VaR 신뢰수준 식별자이지
`annualized_var_percent` 입력값이 아니다. 같은 VaR 문맥에서 공시 결과로 연결된 값을
식별한다. `수익률변동성`만 적힌 값은 주간 수익률의 연환산 표준편차일 수 있으므로 입력으로
인정하지 않는다.

### #122 펀드 수수료

세 계산기는 Product Agent가 상품·클래스·가입 또는 환매 기간에 맞는 요율을 검색 근거로
선택한 뒤 호출한다. 계산기가 모든 상품의 구간표를 내장하거나 구간을 선택하지 않는다.

| 계산기 | 금액 입력 | 산식 | 출력 단위 |
|---|---|---|---|
| `fund_frontend_sales_fee` | `subscription_amount_krw >= 0` | `subscription_amount_krw * selected_rate_percent / 100` | `KRW` |
| `fund_deferred_sales_fee` | `redemption_amount_krw >= 0` | `redemption_amount_krw * selected_rate_percent / 100` | `KRW` |
| `fund_redemption_fee` | `redemption_profit_krw >= 0` | `redemption_profit_krw * selected_rate_percent / 100` | `KRW` |

공통 입력 `selected_rate_percent`는 0~100%이고 `rate_kind = fixed | maximum`을 함께 받는다.
같은 요율 규칙에 “이내” 또는 “상한” 표현이 있을 때만 `rate_kind=maximum`을 허용한다.
고정 요율이면 `fee_amount_krw`, 상한 요율이면 `maximum_fee_amount_krw`를 반환하고 사용하지
않는 출력 키는 `null`이 아니라 생략한다. 상품·클래스 또는 요율 결정에 필요한 보유기간이
확정되지 않으면 계산기를 호출하지 않고 도메인 판단을 `conditional` 또는 `undetermined`로
남긴다.

30일·90일·3년 같은 구간 경계는 Product Agent의 요율 선택 테스트에서 검증한다. Rules
테스트는 기준금액·선택 요율·0%·100%·`rate_kind` 경계만 검증한다. 문서에 없는 반올림은
적용하지 않는다.

## 계산 범위에서 제외한 항목

현재 문서만으로 결정론적 계약을 닫지 못했거나 계산보다 조회에 가까운 항목은 등록하지
않는다.

| 구분 | 항목 | 이유 또는 처리 위치 |
|---|---|---|
| 계약 미확정 | 전체 퇴직소득세 최종 세액 | 누진세율·공제·과세연도·반올림 계약이 더 필요함 |
| 계약 미확정 | DC 부담금 지연이자 | 일수 산입과 연 분모, 적용 구간 계약이 더 필요함 |
| 데이터 계산 | 원시 시계열에서 2.5퍼센타일 추정 | 시계열 품질·관측일 규칙이 없어 현재 입력 범위를 벗어남 |
| 예측 | 수익률·물가·수명 가정 기반 연금 시뮬레이션 | 문서 확정값 계산이 아니라 별도 시뮬레이션 책임임 |
| 직접 조회 | 최초 기준가격 1,000원, 공시된 회전율·거래비용·합성총보수 | 원문 값을 그대로 반환하며 산식 실행이 필요하지 않음 |
| Agent 판단 | 상품별 수수료 구간, 중도인출 사유, 특례 적용 여부 | Product 또는 Policy/Tax Agent가 검색 근거로 확정 |
| 서비스 외 | 규제 준수 한도, 투자 매매·주문 | Calculation Service 책임이 아님 |

## 실행 제한과 오류

- 문자열 수식, DSL, `eval`과 동적 모듈 import를 실행하지 않는다.
- 계산 함수는 네트워크, 파일, 현재 시간, 난수와 환경변수를 읽지 않는다.
- `rules`는 `agent`, `retrieval`, `ingest`를 import하지 않는다.
- 동일한 정규화 입력은 동일한 출력과 warning을 반환한다.

| 오류 | 조건 |
|---|---|
| `CalculatorNotFoundError` | 계산기 ID가 등록되지 않음 |
| `InvalidCalculationInputError` | Pydantic 입력 검증 또는 계산기별 상호 필드 검증 실패 |
| `CalculationExecutionError` | 검증 후 산술 조건을 만족하지 못함 |

입력 오류는 필드 경로와 Pydantic 오류 코드만 보존하며 원시 입력값을 오류 문자열에 넣지
않는다.

## 계산 함수 추가 절차

1. 아래 출처 매핑의 원문에서 산식, 변수, 조건, 단위와 반올림을 직접 대조한다.
2. `extra="forbid"`, `frozen=True`인 Pydantic 입력 모델과 상호 필드 검증을 작성한다.
3. 입력 모델 하나를 받아 `CalculationOutput`을 반환하는 순수 Python 함수를 작성한다.
4. `CalculatorDefinition`을 만들고 `CALCULATORS`에 ID 한 항목을 명시적으로 추가한다.
5. 정상값, 모든 경계의 바로 아래·같음·바로 위, 잘못된 입력, 반올림과 결정성 테스트를
   추가한다.
6. 계산기별 Agent Tool, 입력 출처 label·단위·타입 검증과 도메인 허용 목록을 추가한다.
7. Rules 결과와 Agent 결과의 입출력·출처 키 일치, evidence 연결을 통합 테스트한다.
8. 이 문서의 상태를 `active`로 옮긴다.

## Agent 연결 경계

Calculation Service에는 Agent permission 계층을 넣지 않는다. Agent 계층이 계산기별로
명시적인 Tool schema를 만들고 실제 전달한 Tool만 호출할 수 있게 한다.

현재 허용 목록은 다음과 같다.

| 소비자 | `active` 허용 계산기 |
|---|---|
| Tax/Payout Agent | `pension_withdrawal_limit` |
| Product Agent | `fund_standard_price`, `fund_var_risk` |
| Policy Agent | 없음 |
| Main Supervisor | 직접 호출 금지 |

`AnswerService`는 계산만 있는 답변을 검증된 Python 결과로 교체하고 복합 답변에는 같은 결과를
결정론적으로 덧붙인다. 일부 조건이 없는 도메인 판단은 가능한 계산 결과를 보존하되
`conditional` 또는 `undetermined` 상태와 누락 조건을 유지한다.

## 출처 매핑

이 절이 계산기와 원본 파일 위치를 연결하는 유일한 스펙이다. PDF 쪽수는 PDF 뷰어 기준의
1-based 페이지다. DOCX locator는 Google Drive의 Docling 객체 JSON Pointer이며
`#/texts/N`과 `#/tables/N`도 0부터 시작하는 객체 인덱스 그대로 적는다.

| 상태 | 계산기 | 원본 파일과 locator |
|---|---|---|
| `active` | `pension_withdrawal_limit` | `doc2.pdf` 1쪽 |
| `active` | `fund_standard_price` | `R2_KR510902511M.pdf` 24쪽 |
| `active` | `fund_var_risk` | `R2_KR5160420009.pdf` 20쪽 |
| `planned` | `pension_tax_credit` | `doc41.docx` `#/texts/7`, `#/texts/9`, `#/tables/0`; ISA 결합식은 `doc6.docx` `#/texts/82`, `#/texts/83`, `#/texts/85`, `#/texts/87`, `#/texts/90` |
| `planned` | `pension_income_tax` | `doc38.docx` `#/tables/0`, `#/texts/4`, `#/texts/5`, `#/texts/14`, `#/texts/15`; 부득이한 사유는 `doc20.docx` `#/texts/53`, `#/tables/2` |
| `planned` | `non_pension_withdrawal_tax` | `doc39.docx` `#/texts/22`, `#/tables/0` |
| `planned` | `deferred_retirement_withdrawal_tax` | `doc39.docx` `#/texts/18`, `#/tables/0`; 실제연차 정의는 `doc40.docx` `#/texts/13` |
| `planned` | `pension_withdrawal_allocation`, `pension_withdrawal_tax_breakdown` | `doc39.docx` `#/texts/14`, `#/tables/0`; 상세 순서와 비과세 재원의 한도 소진은 `doc5.pdf` 1~2쪽 |
| `planned` | `pension_withdrawal_limit` 11년차 확장 | `doc2.pdf` 1쪽; 11년차 이후 무제한은 `doc39.docx` `#/texts/7` |
| `planned` | `pension_annual_limit_installment`, `pension_period_installment`, `pension_unit_installment` | `doc2.pdf` 2쪽 |
| `planned` | `dc_medical_withdrawal_threshold` | `doc46.pdf` 1쪽 |
| `planned` | `medical_care_withdrawal_tax_limit`, `medical_care_withdrawal_tax_breakdown` | `doc5.pdf` 1쪽·3쪽; 연령세율·연간합계 예외는 `doc20.docx` `#/texts/53`, `#/tables/2` |
| `planned` | `db_retirement_benefit` | `doc15.pdf` 1쪽 |
| `planned` | `dc_minimum_contribution`, `dc_retirement_benefit` | `doc11.pdf` 1쪽 |
| `planned` | `db_to_dc_transfer_amount` | `doc13.pdf` 2쪽 |
| `planned` | `executive_retirement_income_limit` | `doc45.docx` `#/texts/24`, `#/texts/25`, `#/texts/27`, `#/texts/28`; 지급액 분리는 `#/texts/3`, `#/texts/6` |
| `planned` | `isa_pension_transfer_deadline` | `doc6.docx` `#/texts/51`, `#/texts/57`, `#/texts/74` |
| `planned` | `fund_reported_var_risk` | `R2_KR5160420009.pdf` 20쪽 |
| `planned` | `fund_frontend_sales_fee` | `R2_KR5160420009.pdf` 22쪽 |
| `planned` | `fund_deferred_sales_fee` | `R2_KR5160420009.pdf` 21쪽 |
| `planned` | `fund_redemption_fee` | `R2_KR5194450018.pdf` 7쪽 |

## 검증 위치

- `tests/unit/rules/test_calculation_service.py`
- `tests/unit/rules/test_initial_calculators.py`
- `tests/unit/agent/test_calculation_tools.py`
- `tests/unit/agent/test_domain_agents.py`
- `tests/test_agent_import_boundaries.py`
