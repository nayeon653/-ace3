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
| `pension_withdrawal_limit` | 1~10년차 평가액 ÷ (11 - 수령연차) × 120%, 11년차 이상 한도 미적용 | `doc2.pdf` 1쪽; `doc39.docx` `#/texts/7` |
| `pension_annual_limit_installment` | 연간 잔여한도 ÷ 당해연도 잔여 지급횟수 | `doc2.pdf` 2쪽 |
| `pension_period_installment` | 현재 평가액 ÷ 전체 잔여회차 | `doc2.pdf` 2쪽 |
| `pension_unit_installment` | 잔고좌수 ÷ 전체 잔여횟수 × 1,000좌당 기준가격 ÷ 1,000 | `doc2.pdf` 2쪽 |
| `pension_tax_credit` | 일반 납입 한도(연금저축 600만원·통합 900만원), 소득 경계 16.5%/13.2%, ISA 추가공제(전환액 10%·동일 만기 누적 300만원) | `doc41.docx` 1쪽, `doc6.docx` 3쪽 |
| `pension_income_tax` | 일반 연금수령·부득이한 사유 인출의 연령별 세율과 연간 사적연금소득 1,500만원 경계 | `doc38.docx` `#/tables/0`, `#/texts/4`, `#/texts/5`, `#/texts/14`, `#/texts/15`; `doc20.docx` `#/texts/53`, `#/tables/2` |
| `non_pension_withdrawal_tax` | 세액공제 원금·운용수익의 연금외수령 16.5% | `doc39.docx` `#/texts/22`, `#/tables/0` |
| `deferred_retirement_withdrawal_tax` | 이연퇴직소득의 연금수령 실제수령연차별 납부·감면 비율과 연금외수령 비율 | `doc39.docx` `#/texts/18`, `#/tables/0`; 실제수령연차 정의: `doc40.docx` `#/texts/13` |
| `pension_withdrawal_allocation` | 요청 인출액을 비과세 재원, 이연퇴직소득, 세액공제 원금·운용수익 순서로 배분 | `doc39.docx` `#/texts/14`, `#/tables/0`; 상세 재원 인출 순서: `doc5.pdf` 1~2쪽 |
| `pension_withdrawal_tax_breakdown` | 재원과 연금수령·연금외수령 경로별 인출액·세액·세후액 명세 | `doc39.docx` `#/texts/14`, `#/tables/0`; 비과세 재원의 연금수령한도 소진: `doc5.pdf` 1~2쪽 |
| `dc_medical_withdrawal_threshold` | DC 의료비 중도인출의 재직기간별 적용 임금과 12.5% 금액 기준 | `doc46.pdf` 1쪽; DC 12.5% 기준, 재직기간별 임금 기준, 더 낮은 직전 12개월 임금 적용, IRP 예외 |
| `medical_care_withdrawal_tax_limit` | 의료·요양 인출의 저율과세 한도와 요청액의 한도 내·초과 금액 분리 | `doc5.pdf` 1쪽; 200만원 + 실제 의료비 + 간병비 + 본인 휴직월수 × 150만원 |
| `medical_care_withdrawal_tax_breakdown` | 의료·요양 인출의 한도 내 부득이한 사유 세액·세후액과 미확정 초과액 분리 | `doc20.docx` 1~2쪽; 세법상 3개월 이상 요양, 부득이한 사유 연령별 세율, 관련 연간 1,500만원 예외 |
| `db_retirement_benefit` | 평균일급과 30일 평균임금을 거쳐 검증된 계속근로연수 기준 DB 퇴직급여 계산 | Issue #118; 원본 knowledge locator 미매핑 |
| `dc_minimum_employer_contribution` | 연간임금총액의 12분의 1인 DC 최소 사용자 부담금 계산 | Issue #118; 원본 knowledge locator 미매핑 |
| `dc_retirement_benefit` | 실제 누적 부담금과 부호 있는 누적 운용손익을 합산한 DC 퇴직급여 계산 | Issue #118; 원본 knowledge locator 미매핑 |
| `db_to_dc_transfer_amount` | 두 월 기준 중 큰 값과 검증된 근속연수로 DB→DC 전환금액 계산 | Issue #118; 원본 knowledge locator 미매핑 |
| `fund_standard_price` | (자산총액 - 부채총액) ÷ 총좌수 × 1,000, 소수 셋째 자리 반올림 | `R2_KR510902511M.pdf` 24쪽 |
| `fund_var_risk` | `abs(일간 2.5퍼센타일 손실률) × √250` 후 6단계 상한표 | `R2_KR5160420009.pdf` 20쪽 |
| `fund_reported_var_risk` | 공시된 연환산 97.5% VaR를 추가 변환 없이 6단계 상한표에 적용 | `R2_KR5131420025.pdf` 19~20쪽 |
| `fund_frontend_sales_fee` | 납입금액 × 선택 요율 ÷ 100, `fixed`면 `fee_amount_krw`만 반환 | `R2_KR5160420009.pdf` 21쪽 |
| `fund_deferred_sales_fee` | 환매금액 × 선택 요율 ÷ 100, `maximum`이면 `maximum_fee_amount_krw`만 반환 | `R2_KR5160420009.pdf` 21쪽 |
| `fund_redemption_fee` | 이익금 × 선택 요율 ÷ 100 | `R2_KR5194450018.pdf` 30쪽(이익금 정의), 34쪽(클래스·보유기간별 요율표) |

검증 문서 정보는 개발 기록이며 런타임 결과에 직렬화하지 않는다. 문서에 없는 표시
자릿수나 최종 지급 단위 반올림은 임의로 적용하지 않고 warning에 남긴다.

### 공시 연환산 VaR 위험등급 계약

**입력과 산술**: `fund_reported_var_risk`는 공시 문서에 결과값으로 명시된
`annualized_var_percent` 하나를 받는다. 입력은 0 이상의 유한한 `Decimal`이어야 하며 생략,
명시적 `null`, 음수와 extra 입력을 거부한다. 이미 연환산된 값을 그대로 사용하므로 √250을
다시 곱하거나 반올림하지 않는다. Rules는 `> 50`, `> 30`, `> 20`, `> 10`, `> 1` 순서의
경계를 적용한다. 따라서 경계값 50, 30, 20, 10, 1은 각각 2, 3, 4, 5, 6등급이고 0도
6등급이다. Agent와 presentation은 이 결과를 다시 계산하지 않는다.

**기존 일간 VaR와의 구분**: `fund_var_risk`는 실제 일간 2.5퍼센타일 손실률을 입력받아
절대값과 √250으로 연환산하는 기존 경로다. `fund_reported_var_risk`는 문서가 이미 산출한
연환산 97.5% VaR 결과를 받는 경로다. 공시 연환산 값을 `fund_var_risk`에 전달하거나 두
계산기를 연결해 중복 연환산하지 않는다.

**책임과 provenance 경계**: Product Agent는 상품명과 상품코드·식별자, 필요한 경우 share
class, 공시 기준일, reported annualized VaR인지 daily/raw VaR인지를 확인한 뒤 의미에 맞는
Tool 하나를 선택한다. 상품코드를 이름보다 강한 식별자로 사용하고, 유사한 상품명이나 다른
상품·class의 근거를 재사용하지 않는다. 현재 검색 metadata로 공시 날짜를 신뢰성 있게 비교할
수 없는 `현재`·`최신` 요청은 검색 순위로 추정하지 않고 `최신 공시 기준일 확인 필요`인
conditional 결과로 남긴다.

Tool은 같은 출처 구절에 공시·연환산·97.5% VaR 의미와 정확한 단일 수치가 함께 있는지
검증한다. VaR와 변동성·표준편차·위험등급 숫자, 다른 상품·class, 과거 공시, 근사값·범위·
부등식·부정 표현은 서로 대체하지 않는다. 상품·class·공시 기준·VaR 의미와 값이 각각
명확한 경우에만 같은 source를 재사용한다. Rules는 검증된 `Decimal` 값의 등급 판정만
담당하고 presentation은 Rules 결과를 그대로 표시한다. Main Supervisor의 routing은 변경하지
않는다.

검증 locator는 corpus manifest의 `KR5131420025` →
`data/raw/prospectus/KR5131420025/R2_KR5131420025.pdf` 매핑을 따르며, 19쪽은 최근 결산일
기준 연환산 최대손실예상액과 등급을, 20쪽은 97.5% VaR 6단계 경계표를 제공한다.

### 연금수령한도·분할지급 계산 계약

**`pension_withdrawal_limit`**: `pension_year`는 상한 없는 1 이상의 정수다.
1~10년차에는 `account_valuation_krw`(0 이상의 `Decimal`, KRW)가 필수이며
`withdrawal_limit = account_valuation_krw / (11 - pension_year) * 1.2`와
`limit_applies=true`를 반환한다. 11년차 이상에는 평가액을 생략할 수 있고
`withdrawal_limit=null`(단위 KRW), `limit_applies=false`를 반환한다. 이 구간에 평가액이
전달돼도 한도 계산에는 사용하지 않고 warning으로 알린다. `null`을 0원, 무한대나 임의의
큰 수로 바꾸지 않는다.

**`pension_annual_limit_installment`**: 필수 입력은 0 이상의 `Decimal`인
`remaining_annual_limit_krw`(KRW)와 1 이상의 정수인
`remaining_payments_in_year`다. 출력은
`installment_krw = remaining_annual_limit_krw / remaining_payments_in_year`(KRW)다.

**`pension_period_installment`**: 필수 입력은 0 이상의 `Decimal`인
`current_valuation_krw`(KRW)와 1 이상의 정수인 `remaining_payments`다. 출력은
`installment_krw = current_valuation_krw / remaining_payments`(KRW)다. 현재 입력으로
해당 연도의 지급액만 계산하며 다음 연도 평가액을 추정하지 않는다.

**`pension_unit_installment`**: 필수 입력은 0 이상의 `Decimal`인 `remaining_units`(좌),
1 이상의 정수인 `remaining_payments`, 0 이상의 `Decimal`인
`standard_price_per_1000_units_krw`(KRW/1,000좌)다. 출력은
`installment_krw = remaining_units / remaining_payments *
standard_price_per_1000_units_krw / 1000`(KRW)다.

**입력·산술 경계**: 선택 평가액의 생략과 명시적 `null`은 구분하며 명시적 `null`, 음수와
extra 입력은 거부한다. 필수 입력의 `null`도 거부한다. 금액·좌수·기준가격 0은 허용해 0
결과를 반환하지만 지급횟수 0이나 음수는 입력 검증에서 거부하므로 0으로 나누지 않는다.
연금수령한도 역시 11년차 이상을 산식에 대입하지 않아 0 또는 음수 분모로 나누지 않는다.
모든 산술은 `Decimal`로 수행하며 문서에 없는 원·좌수 단위 반올림·절사를 적용하지 않는다.

**책임·출처·호출 경계**: 지급 방식의 적용 가능 여부와 필요한 기준시점 입력 확인은 Agent,
값/source의 같은 구절 의미·수량·단위 대응 검증은 Tool, 확정 입력의 산술은 Rules가
담당한다. 한도용 `pension_year`를 이연퇴직소득세의 `actual_pension_receipt_year`와
혼용하지 않고, 당해연도 `remaining_payments_in_year`를 전체 기간
`remaining_payments`와 혼용하지 않는다. 검증된 input source와 검색 청크 ID는 계산의
`input_sources`와 최종 evidence에 보존한다. 각 Tool은 최대 한 번 호출하며 #116 계산
Tool은 한 응답에서 하나만 실행하고 하나를 계산한 뒤에는 다른 #116 Tool을 추가 실행하지
않는다.

### `pension_tax_credit` 계약

**필수 입력**: `pension_savings_net_contribution_krw`(연금저축 순납입액),
`retirement_pension_net_contribution_krw`(퇴직연금 순납입액), `pension_savings_isa_transfer_krw`,
`retirement_pension_isa_transfer_krw`(ISA 만기자금 전환액, 명시적 `0` 허용).

**선택 입력**: `prior_same_maturity_isa_extra_eligible_contribution_used_krw`
(같은 만기자금의 전년도 추가 공제대상액 사용분, 0~300만원), `income_basis`(`salary` 또는
`comprehensive_income`), `income_amount_krw`(소득금액), `remaining_tax_before_pension_credit_krw`
(연금계좌 세액공제 적용 직전 잔여 산출세액).

**생략/0/null 계약**: `pension_savings_isa_transfer_krw`, `retirement_pension_isa_transfer_krw`는
필수이므로 생략하면 입력 오류이고, 명시적 `0`은 허용한다. 나머지 선택 입력은 필드 자체를
생략하는 것과 값 `0`을 명시적으로 전달하는 것을 다르게 취급한다. 생략은 "정보 없음"이고
`0`은 "확인된 값이 0"이라는 뜻이다. Pydantic 입력 모델은 명시적 `null` 전달을 거부한다
(`reject_explicit_null` 검증기) — 값이 없으면 필드를 아예 포함하지 않아야 한다. ISA
전환액이 하나라도 0보다 크면 `prior_same_maturity_isa_extra_eligible_contribution_used_krw`가
필수이고, ISA 전환액이 모두 0이면 이 필드를 포함할 수 없다. `income_basis`와
`income_amount_krw`는 항상 함께 있거나 함께 생략해야 하며,
`remaining_tax_before_pension_credit_krw`는 소득 기준이 있을 때만 허용한다.
`CalculationResult.inputs`에는 실제로 전달된(생략되지 않은) 필드만 남는다(`exclude_unset`).

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

### `pension_income_tax` 계약

**필수 입력**: `pension_treatment`(`ordinary` 또는 `unavoidable`), `recipient_age`(0 이상의
정수). `ordinary`는 `recipient_age >= 55`이고 `is_lifetime_annuity`가 필수다.

**선택 입력**: `target_taxable_amount_krw`, `is_lifetime_annuity`,
`annual_private_pension_taxable_income_krw`. `is_lifetime_annuity`와 연간 합계는
`ordinary`에서만 받으며 `unavoidable`에 전달하면 입력 오류다. 대상액과 연간 합계가 함께
있으면 대상액은 연간 합계보다 작거나 같아야 한다.

Tool provenance에서 `target_taxable_amount_krw`는 현재·이번·해당 인출 또는 수령의
과세대상액과 정확한 금액이 같은 구절에 있어야 한다. `ordinary`는 현재 연금수령 의미를,
`unavoidable`은 부득이한 사유로 인출한 현재 대상액 의미를 요구한다. 반대로
`annual_private_pension_taxable_income_krw`는 연간·사적연금·과세대상·합계 의미를 같은
구절에서 요구한다. 연간·합계·전체 사적연금소득 구절은 현재 대상액 source로 사용할 수
없고 동일 source를 두 필드에 재사용할 수 없다.

수령 유형과 종신 여부는 같은 구절의 `아님`, `아닌`, `아니다`, `해당하지 않음`,
`해당하지 않는다` 같은 부정 표현을 먼저 판정한다. 다만 종신연금이 아니라는 명시적 표현은
`is_lifetime_annuity=false`의 근거로 허용한다. `recipient_age`는 `나이 N세`, `연령 N세`,
`만 N세`처럼 정확한 단일 나이만 허용한다. 이상·이하·초과·미만, 범위(`55~69세`,
`55세부터 69세`)와 근사(`70세 전후`) 표현은 정확한 나이 source로 사용하지 않고
생년월일에서 나이를 계산하거나 추정하지 않는다.

**생략/0/null/음수 계약**: 선택 필드 생략은 정보가 확인되지 않았다는 뜻이고 명시적 `0`은
확인된 값으로 보존한다. 명시적 `null`, 음수 금액·나이와 정의되지 않은 extra 입력은
거부한다. `CalculationResult.inputs`에는 실제 전달한 필드만 남는다.

**일반 연금수령 세율**: 종신연금은 나이와 관계없이 3.3%, 비종신은 55~69세 5.5%,
70~79세 4.4%, 80세 이상 3.3%다. `base_rate_percent`에 적용 기본세율을 반환한다.

**연간 합계 경계**: 연간 합계는 현재 대상액을 포함한 전 금융기관의 과세대상 사적연금소득
합계이며 세액공제를 받지 않은 원금과 이연퇴직소득은 제외한다.

- 합계 생략: `annual_threshold_status=unknown`. 대상액이 있어도 `tax_krw`와
  `after_tax_krw`를 생성하지 않는다.
- 15,000,000원 이하(정확히 15,000,000원 포함): `annual_threshold_status=within`,
  `filing_choice_required=false`. 대상액이 있으면 기본세율로 세액과 세후 금액을 계산한다.
- 15,000,000원 초과: `annual_threshold_status=exceeded`,
  `filing_choice_required=true`. `separate_tax_option_rate_percent=16.5`와 연간 합계 전체에
  16.5%를 적용한 `separate_tax_option_tax_krw`, `separate_tax_option_after_tax_krw`를
  반환한다. 초과분이나 현재 대상액에 16.5%를 적용하지 않으며 종합과세 최종세액과 현재
  대상액의 확정 세액을 생성하지 않는다.

**부득이한 사유 인출**: 70세 미만 5.5%, 70~79세 4.4%, 80세 이상 3.3%이며 55세 미만도
허용한다. 연간 1,500만원 기준은 적용하지 않고 대상액이 있을 때만 `tax_krw`와
`after_tax_krw`를 반환한다. 해당 사유의 법률상 적격성은 Agent가 판단한다.

### `non_pension_withdrawal_tax` 계약

**선택 입력**: `taxable_amount_krw`. 생략하면 `base_rate_percent=16.5`만 반환하고 명시적
`0`이면 0원 세액과 세후 금액을 반환한다. 명시적 `null`, 음수와 다른 계산기의 extra 입력은
거부한다. 금액이 있으면 `tax_krw = taxable_amount_krw × 16.5%`,
`after_tax_krw = taxable_amount_krw - tax_krw`를 반환한다.

이 계산기는 세액공제를 받은 원금·운용수익의 연금외수령에만 사용한다. 나이, 연간 합계,
이연퇴직소득 입력을 받지 않으며 재원 적격성은 Agent가 판단한다.

### 연금소득세 계산 공통 경계

두 계산기는 금액과 세율을 `Decimal`로만 계산하고 원문에 없는 원 단위 반올림·절사를
적용하지 않는다. Rules는 확정된 입력의 검증과 산술만 담당하고 검색, LLM, 외부 API,
법률상 사유·재원 추론을 수행하지 않는다. Tool은 선택 값/source 쌍과 같은 구절의 의미·값
대응을 검증하고, Agent는 계산기 선택과 법률상 적격성·누락 조건을 판단한다.

일반적으로 계산 Tool은 하나만 실행한다. 연금수령과 연금외수령 비교 질문에 한해
`calculate_pension_income_tax`과 `calculate_non_pension_withdrawal_tax`을 각각 최대 한 번
실행하고 두 결과를 함께 보존한다. 일반 연금수령의 연간 합계가 없어
`annual_threshold_status=unknown`이면 Python 결과 경계가 `status=conditional`과 연간 합계
확인 조건을 강제한다. `filing_choice_required=true`이면 같은 경계가 `status=conditional`과
종합과세 또는 16.5% 분리과세 선택 조건을 강제한다. 금액이 생략된 단순 세율 질문에는
금액 누락 조건을 추가하지 않는다.

### `deferred_retirement_withdrawal_tax` 계약

**필수 입력**: `receipt_type`(`pension` 또는 `non_pension`). `pension`이면 1 이상의 정수인
`actual_pension_receipt_year`도 필수이고, `non_pension`이면 이 필드를 전달할 수 없다.
`actual_pension_receipt_year`는 실제로 연금을 수령한 연도의 누적 횟수다. 같은 해 여러 번
수령해도 한 해로 세고 수령하지 않은 연도는 누적하지 않는다. 연금수령한도 계산기의
`pension_year`와 의미가 다르며 서로 대신 사용하거나 함께 전달할 수 없다.

**선택 입력**: `allocated_deferred_retirement_tax_krw`(해당 인출분에 이미 배분된
이연퇴직소득세). 생략하면 비율만 반환하고 명시적 `0`은 확인된 배분세액으로 보존해
납부세액과 감면세액을 모두 0원으로 반환한다. 명시적 `null`, 음수와 정의되지 않은 extra
입력은 거부한다.

**납부·감면 비율**: 연금수령 실제수령 1~10년은 70%/30%, 11~20년은 60%/40%, 21년
이상은 50%/50%다. 연금외수령은 100%/0%다. `payable_ratio_percent`와
`reduction_ratio_percent`는 항상 반환한다. 배분세액이 있을 때만
`tax_payable_krw = 배분세액 × 납부 비율`,
`tax_reduction_krw = 배분세액 - tax_payable_krw`를 반환한다. 계좌 전체 퇴직소득세의
원액 산출, 부분 인출분 안분, 인출 원금과 세후 인출액 계산은 범위 밖이다.

**책임과 실행 경계**: Rules는 확정된 입력의 교차검증과 `Decimal` 산술만 수행하고 문서에
없는 반올림·절사를 적용하지 않는다. Tool은 값/source 쌍을 요구하며 수령 유형,
실제수령연차와 해당 인출분에 배분된 세액의 의미·값이 원문 같은 구절에 대응하는지
검증하고 출처를 보존한다. Agent는 검색 근거에서 실제수령연차와 배분세액을 확인하고
이연퇴직소득 재원을 다른 재원 계산기와 혼용하지 않는다. 이 Tool은 실행당 최대 한 번만
호출하며 다른 계산 Tool과 동시에 실행하지 않고, 계산 뒤에는 submit만 허용한다. 납부·감면
세액 질문인데 배분세액이 없으면 Agent가 조건부 결과와 확인 필요 조건을 제출하지만 단순
비율 질문은 비율만으로 확정할 수 있다.

### 연금 인출 재원 배분·세금 명세 계약

**`pension_withdrawal_allocation`**: `requested_withdrawal_krw`를
`tax_free_source_balance_krw`, `deferred_retirement_source_balance_krw`,
`credited_and_earnings_source_balance_krw` 순서로 배분하는 결정론적 Rules 함수다. 각 재원의
인출액과 인출 후 잔여액을 반환한다. 요청액이 세 재원의 전체 가용 잔액보다 크면 입력
오류이며, 확인되지 않은 잔액을 0으로 간주하지 않는다. 모든 금액과 산술은 `Decimal`을
사용한다.

**`pension_withdrawal_tax_breakdown`**: allocation과 기존 `pension_income_tax`,
`non_pension_withdrawal_tax`, `deferred_retirement_withdrawal_tax` 순수 함수를 함수 내부에서
조합하며 Agent의 Tool chaining으로 계산하지 않는다. 재원과 pension/non-pension 처리 경로별
인출액·세액·세후액, 현재 인출 합계 세액·세후액을 반환한다. 해당하면 연간 전체 과세대상
사적연금소득 기준 16.5% 분리과세 선택세액도 별도 필드로 반환한다.

연간 과세대상 사적연금 합계가 확인되지 않아 현재 세액을 확정할 수 없으면 경로 및 현재
인출 합계의 세액·세후액에 `null`을 전파한다. 연간 합계가 1,500만원을 초과해 종합과세와
16.5% 분리과세 중 선택해야 하는 경우에도 연간 선택세액은 현재 인출 세액과 별도 의미로
유지한다. 비과세 재원 인출도 연금수령한도를 소진한다는 warning을 보존한다. 모든 산술은
`Decimal`로 수행하고 문서에 없는 반올림·절사를 적용하지 않는다.

**Tool·provenance 책임 경계**: Agent는 사용자 의도, 조건, 지급 방식, 재원 의미와 근거를
판단한다. `calculate_pension_withdrawal_allocation`과
`calculate_pension_withdrawal_tax_breakdown` Tool은 입력값과 source의 의미·수량·구절 대응을
검증하고, Rules는 검증된 입력만으로 결정론적 계산을 수행한다. Presentation은 Rules 결과를
재계산하지 않고 표현한다.

Tool provenance는 요청 인출액, 각 재원 잔액과 의미, pension/non-pension 처리액, 현재
인출액과 연간 합계의 구분, 이연퇴직소득의 pension/non-pension 배분세액, 계좌 전체 세액과
해당 인출분 배분세액의 구분을 검증한다. 나이는 정확한 값과 범위 표현을 구분하고, 부정
표현과 실제수령연차도 원문 같은 구절에서 확인한다.

### 의료비·요양 인출 계산 계약

**`dc_medical_withdrawal_threshold`**: DC 의료비 중도인출의 12.5% 금액 기준을 계산한다.
재직기간은 1년 이상과 1년 미만의 범주형 입력으로 구분한다. 1년 이상은 직전연도
연간임금총액을 기본으로 하되 증빙된 신청일 직전 12개월 임금이 더 낮으면 그 값을 적용하고,
1년 미만은 재직 중 월평균 급여에 12를 곱한 연환산 임금을 적용한다. 증빙 의료비가 적용
임금의 12.5%를 엄격히 초과할 때만 `threshold_met=true`이며 정확히 같으면 `false`다.

IRP에는 이 DC 12.5% 기준을 적용하지 않는다. 다만 그 예외만으로 IRP 중도인출 가능 여부를
확정하지 않는다. 최종 eligibility, DC의 6개월 요양 조건, 가족관계와 서류·증빙 적정성은
Policy Agent가 판단한다.

**`medical_care_withdrawal_tax_limit`**: 저율과세 한도는 200만원에 실제 의료비, 간병비,
본인의 휴직월수당 150만원을 더한 금액이다. `requested_withdrawal_krw`는 이번 의료·요양
사유의 총 요청 인출액이며, 요청액을 한도 내 금액과 초과액으로 분리한다. 요청액이 한도와
같으면 전액 한도 내 금액이고 초과액은 0이다. 이 함수는 초과액의 세액을 계산하지 않는다.
이 한도는 #116 일반 연금수령한도와 다른 제도이며, 재난피해처럼 별도 금액한도가 없는
사유에 임의로 적용하지 않는다.

**`medical_care_withdrawal_tax_breakdown`**: 위 limit Rules를 내부 호출하고 한도 내 금액에
기존 `pension_income_tax`의 `unavoidable` 경로 순수 함수를 조합한다. Agent의 Tool
chaining이 아니며 #114·#115·#116 계산기를 임의로 호출하지 않는다. 정확한 수령자 나이에
따른 부득이한 사유 세율을 적용하며, 이 경로에는 일반 연금수령의 연간 사적연금소득
1,500만원 기준을 적용하지 않는다.

초과액이 0이면 현재 인출 전체의 세액과 세후액을 확정한다. 초과액이 0보다 크고 그 재원 및
연금수령·연금외수령 구분이 확인되지 않으면 초과액 세액을 추정하지 않고 현재 전체 세액과
세후액에 `null`을 전파하며 warning을 보존한다. 세법상 3개월 이상 요양에 따른 부득이한
사유 과세와 DC eligibility의 6개월 요양 조건은 서로 다른 판단으로 유지한다.

**책임 경계**: Policy Agent는 DC/IRP 구분, DC 중도인출 사유, 6개월 요양, 가족관계와
서류·증빙 적정성을 판단한다. Tax/Payout Agent는 세법상 3개월 요양과 부득이한 사유,
limit와 breakdown 선택 및 과세 의미를 판단한다. Main Supervisor는 가능 여부와 세금을
함께 묻는 복합 질문을 Policy와 Tax/Payout으로 라우팅할 뿐 기간을 직접 판정하거나 세액을
계산하지 않는다. Tool은 값/source의 의미·수량·동일 구절 대응을 검증하고, Rules는 검증된
값으로 결정론적 `Decimal` 산술만 수행한다. Presentation은 Rules 결과를 재계산하지 않고
표현한다.

**입력 provenance**: Tool은 재직 1년 이상·미만의 의미, 직전연도 연간임금과 신청일 직전
12개월 임금의 구분, 재직 중 월평균 급여, DC 증빙 의료비, 이번 사유 요청 인출액, 실제
의료비, 간병비, 본인의 휴직월수와 정확한 수령자 나이를 검증한다. 부정 표현, 근사·범위
표현과 다른 사람의 정보는 해당 입력 근거로 사용하지 않는다. 같은 source는 각 필드의
의미와 값이 모두 확인될 때만 재사용하며 정보 부재를 명시적 0으로 바꾸지 않는다.

세 계산기는 모든 금액을 `Decimal`로 계산하고 문서에 없는 반올림·절사를 적용하지 않는다.

### DB·DC 퇴직급여 계산 계약

**`db_retirement_benefit`**: 평균일급은 평균임금 산정 대상 최근 3개월 임금 합계를 검증된
포함 일수로 나누고, 30일 평균임금은 평균일급에 30을 곱한다. DB 퇴직급여는 30일
평균임금에 검증된 계속근로연수를 곱한다. 평균일급과 30일 평균임금을 중간 결과로
보존한다. 포함 일수는 1 이상이며 평균임금 제외기간 반영을 끝낸 값이고, 계속근로연수는
상위 계층에서 검증된 0 이상의 `Decimal`이다. Rules는 제외기간을 판단하거나 날짜에서
근속연수를 계산하지 않고 부분연수를 절사하지 않는다.

**`dc_minimum_employer_contribution`**: 0 이상의 연간임금총액을 12로 나눈 값을 DC 최소
사용자 부담금으로 반환한다. 명시적 0은 0으로 보존한다. 실제 납입액·미납액을 판정하지
않고, 원문 괄호가 불명확한 육아휴직 특수 산식을 추가하지 않는다.

**`dc_retirement_benefit`**: 0 이상의 실제 누적 부담금에 부호 있는 누적 운용손익을
더한다. 운용손익은 양수, 0과 음수를 허용한다. 결과가 음수여도 문서에 없는 0 하한을
적용하지 않고 warning과 함께 음수 결과를 보존한다. 수익률이나 예상 손익을 금액 대신
사용하지 않는다.

**`db_to_dc_transfer_amount`**: 최종 30일 평균임금과 `최종 연간임금총액 / 12` 중 큰 월
기준을 선택해 검증된 근속연수를 곱한다. 두 기준이 같으면 `selected_basis_type=equal`로
별도 보존하고 어느 한쪽이 더 크다고 표현하지 않는다. Rules는 전환 가능 여부를 판단하거나
날짜에서 근속연수를 만들지 않는다.

네 계산기는 `Decimal` 결정론적 산술을 사용하고 문서에 없는 반올림·절사를 적용하지
않는다. 네 Calculation Tool도 각각 같은 의미의 Rules 하나만 호출하며 다른 급여나 세금
계산으로 fallback하지 않는다. 현재 구현 산식은 Issue #118을 기준으로 검증했으며, 정확한
원본 knowledge 문서 filename과 locator는 저장소에서 확인되지 않아 추측해 연결하지 않았다.

**책임 경계**: Policy Agent는 DB/DC 제도 유형, 평균임금 제외기간, 계속근로·근속 인정과
DB→DC 전환 가능 여부를 판단한다. Tax/Payout Agent는 요청 의미에 맞는 #118 Tool을 선택하고
급여·최소 부담금·전환금액 결과를 소비한다. Tool은 값/source의 의미·단위·기간 대응을
검증하고 Rules는 검증된 입력으로 산술만 수행한다. Main Supervisor는 제도 판단만 있으면
Policy, 금액만 있으면 Tax/Payout, 둘 다 있으면 두 Domain으로 라우팅하며 기간·근속연수·
급여·세금을 직접 계산하지 않는다. Presentation은 Python 결과를 재계산하지 않고 표현한다.

**입력 provenance**: 최근 3개월 평균임금 대상 임금은 연간임금총액과 다르고,
연간임금총액은 전환 기준 최종 연간임금총액과 다르다. 평균일급, 30일 평균임금과 일반
월급을 서로 바꾸지 않는다. 평균임금 포함 일수는 근속기간이나 휴직기간이 아니다. DC 최소
사용자 부담금은 실제 누적 부담금이 아니며, 실제 누적 부담금은 DC 계좌잔액이 아니다.
운용손익 금액을 수익률로부터 추정하지 않고, #117 의료비 threshold용 임금을 #118 임금
입력으로 재사용하지 않는다.

계속근로·근속연수는 정확한 값만 사용하고 범위·근사·부정 표현은 거부한다. 같은 source는
각 필드의 의미와 정확한 값이 모두 명시된 경우에만 재사용한다. 명시적 0은 정보 부재와
구분하고, 음의 운용손익은 손실 표현과 부호 의미까지 검증한다.

**급여와 세금 경계**: #118은 퇴직소득세 전체 계산을 포함하지 않는다. 급여 계산 결과는
보존하되, 세금까지 요청받아도 현재 저장소에 최초 퇴직소득세를 산출할 정확한 계산 계약이
없으면 세금 숫자를 생성하지 않는다. 의미가 비슷하다는 이유로 기존 인출 세금 Tool을
연쇄 호출하지 않고 세금 부분은 추가 입력과 별도 계산이 필요한 조건부 상태로 유지한다.

### 펀드 수수료 계산 계약

**`fund_frontend_sales_fee`**: 가입 시 납입금액에 검증된 선취판매수수료율을 곱한다. 필수
입력은 0 이상의 `Decimal`인 `subscription_amount_krw`(KRW), 0~100의 `Decimal`인
`selected_rate_percent`(%), `rate_kind`(`fixed` 또는 `maximum`)다. 산식은
`subscription_amount_krw × selected_rate_percent / 100`이다.

**`fund_deferred_sales_fee`**: 환매 시 환매금액에 검증된 후취판매수수료율을 곱한다. 필수
입력은 0 이상의 `redemption_amount_krw`(KRW), `selected_rate_percent`, `rate_kind`다.
산식은 `redemption_amount_krw × selected_rate_percent / 100`이다.

**`fund_redemption_fee`**: 환매 시 이익금에 검증된 환매수수료율을 곱한다. 필수 입력은
0 이상의 `redemption_profit_krw`(KRW), `selected_rate_percent`, `rate_kind`다. 산식은
`redemption_profit_krw × selected_rate_percent / 100`이다.

**출력 계약**: `rate_kind=fixed`면 `fee_amount_krw`만 반환하고 `maximum_fee_amount_krw`
키는 생략한다. `rate_kind=maximum`이면 그 반대다. 두 키를 동시에 반환하거나 사용하지 않는
키를 `null`로 채우지 않는다. 문서에 없는 원 단위 반올림·절사는 적용하지 않는다.

**세 계산기는 서로 대체 관계가 아니다**: 선취판매수수료는 납입금액, 후취판매수수료는
환매금액, 환매수수료는 이익금을 기준으로 하며 서로 다른 계산이다. 판매보수·총보수·
운용보수·신탁보수·기타비용·총비용비율(TER)의 수치를 이 세 계산기의
`selected_rate_percent`로 사용하지 않는다. Rules는 이 세 fee를 서로 합산하거나 다른
보수·비용과 합산하지 않는다.

**fixed vs maximum**: 요율 문구에 "이내", "상한", "최대" 표현이 있으면 `rate_kind=maximum`
이며 그 결과는 상한일 뿐 실제 부과금액이 아니다. 그런 표현 없이 확정 요율만 있으면
`rate_kind=fixed`다. 실제 적용 요율이 확인되지 않고 상한 요율만 문서에 있으면 상한 계산
결과는 보존하되 실제 적용 수수료율은 별도로 확인해야 한다.

**책임 경계**: 상품·클래스·판매채널과 가입 또는 환매 시점의 보유기간에 맞는 요율 선택은
Product Agent가 검색 근거에서 확정하고, Rules는 구간표를 내장하거나 구간을 선택하지
않는다. Tool은 값/source의 fee 종류·금액 의미·요율 의미·`rate_kind` 의미 대응을
검증한다. Presentation은 Rules 결과를 재계산하지 않고 존재하는 출력 키만 표현한다.

**입력 provenance**: 납입금액, 환매금액, 이익금은 서로 다른 의미이며 평가금액·원금·
수익률로 대체하지 않는다. 선취판매수수료율, 후취판매수수료율, 환매수수료율은 각 계산기
전용 라벨로만 확인하고 다른 계산기의 요율 라벨이나 판매보수·총보수 등 집계 비용 표현은
요율 source로 인정하지 않는다.

원본 문서에서 선취·후취판매수수료는 클래스별로 "이내" 상한 요율(예:
납입금액의 0.10% 이내)로, 환매수수료는 30일·90일 보유기간 구간별 이익금 기준 고정
비율(예: 30일 미만 이익금의 70%)로 각각 확인했으며, 두 rate_kind가 실제 문서에 모두
존재한다.

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
| Tax/Payout Agent | `pension_withdrawal_limit`, `pension_annual_limit_installment`, `pension_period_installment`, `pension_unit_installment`, `pension_tax_credit`, `pension_income_tax`, `non_pension_withdrawal_tax`, `deferred_retirement_withdrawal_tax`, `pension_withdrawal_allocation`, `pension_withdrawal_tax_breakdown`, `medical_care_withdrawal_tax_limit`, `medical_care_withdrawal_tax_breakdown`, `db_retirement_benefit`, `dc_minimum_employer_contribution`, `dc_retirement_benefit`, `db_to_dc_transfer_amount` |
| Product Agent | `fund_standard_price`, `fund_var_risk`, `fund_reported_var_risk`, `fund_frontend_sales_fee`, `fund_deferred_sales_fee`, `fund_redemption_fee` |
| Policy Agent | `dc_medical_withdrawal_threshold` |
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
- `tests/unit/rules/test_fund_reported_var_risk.py`
- `tests/unit/rules/test_pension_installments.py`
- `tests/unit/rules/test_pension_tax_credit.py`
- `tests/unit/rules/test_pension_income_tax.py`
- `tests/unit/rules/test_deferred_retirement_withdrawal_tax.py`
- `tests/unit/rules/test_pension_withdrawal_breakdown.py`
- `tests/unit/rules/test_medical_care_withdrawal.py`
- `tests/unit/agent/test_calculation_tools.py`
- `tests/unit/agent/test_domain_agents.py`
- `tests/test_agent_import_boundaries.py`
