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
| `pension_income_tax` | 일반 연금수령·부득이한 사유 인출의 연령별 세율과 연간 사적연금소득 1,500만원 경계 | `doc38.docx` `#/tables/0`, `#/texts/4`, `#/texts/5`, `#/texts/14`, `#/texts/15`; `doc20.docx` `#/texts/53`, `#/tables/2` |
| `non_pension_withdrawal_tax` | 세액공제 원금·운용수익의 연금외수령 16.5% | `doc39.docx` `#/texts/22`, `#/tables/0` |
| `deferred_retirement_withdrawal_tax` | 이연퇴직소득의 연금수령 실제수령연차별 납부·감면 비율과 연금외수령 비율 | `doc39.docx` `#/texts/18`, `#/tables/0`; 실제수령연차 정의: `doc40.docx` `#/texts/13` |
| `fund_standard_price` | (자산총액 - 부채총액) ÷ 총좌수 × 1,000, 소수 셋째 자리 반올림 | `R2_KR510902511M.pdf` 24쪽 |
| `fund_var_risk` | `abs(일간 2.5퍼센타일 손실률) × √250` 후 6단계 상한표 | `R2_KR5160420009.pdf` 20쪽 |

검증 문서 정보는 개발 기록이며 런타임 결과에 직렬화하지 않는다. 문서에 없는 표시
자릿수나 최종 지급 단위 반올림은 임의로 적용하지 않고 warning에 남긴다.

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
| Tax/Payout Agent | `pension_withdrawal_limit`, `pension_tax_credit`, `pension_income_tax`, `non_pension_withdrawal_tax`, `deferred_retirement_withdrawal_tax` |
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
- `tests/unit/rules/test_pension_income_tax.py`
- `tests/unit/rules/test_deferred_retirement_withdrawal_tax.py`
- `tests/unit/agent/test_calculation_tools.py`
- `tests/unit/agent/test_domain_agents.py`
- `tests/test_agent_import_boundaries.py`
