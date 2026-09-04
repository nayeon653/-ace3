# Tax/Payout Agent 스펙

## 목적과 책임

Tax/Payout Agent는 연금 세액공제, 과세와 수령 조건을 제공 문서 근거로 판단한다.
검증된 입력이 있으면 Python Calculation Tool로 연금수령한도, 연금계좌 세액공제,
분할지급액, 연금수령 세금 또는 연금외수령 세금을 계산한다. 일반적으로 질문에 맞는 Tool 하나만
호출하고, 연금수령·연금외수령 비교 질문에서는 두 세금 Tool을 각각 한 번 호출할 수 있다.

세액공제 적용 조건, 연금 과세, 수령 방식(일시금/분할)에 따른 과세, 중도해지 과세는 이
Agent의 책임이다. 상품의 위험·비용·수익률은 Product, 계좌 이전·가입·해지 절차 자체는
Policy 책임이며 이 Agent는 해당 질문을 `not_applicable`로 제출한다(중도해지로 발생하는
과세 판단 자체는 예외로 이 Agent 책임에 남는다).

## 모델과 구현

| 항목 | 값 |
|---|---|
| 구현 | 독립 `create_agent` 기반 ReAct graph |
| 모델 | `HCX-007` |
| Thinking | `none` |
| temperature / 최대 토큰 | `0.1` / `1024` |
| Provider timeout/retry | 호출당 30초, 최대 2회 retry |
| 프롬프트 | `pension_agent/prompts/domain/tax-payout-agent.md` |
| 구현 | `pension_agent/agent/tax_payout/` |

## 입력과 출력

입력은 `DomainRequest {question, objective}`다. 출력은 `domain=tax_payout`인 공통
`DomainResult`다. 계산을 실행한 결과에는 calculator ID, 정규화 입력, 출력, 단위와
warning이 `calculations`에 포함된다.

## Tool과 문서 접근

### `search_documents`

- `not_applicable` 판단 외에는 `submit_domain_result` 전에 반드시 한 번 호출해야 하며
  `pension_reference` 문서만 검색한다.
- 문서명과 청크 ID는 사용자 질문 원문에 실제 포함된 경우에만 힌트로 사용한다.
- 검색 방식과 결과 수는 Search Service가 결정한다.

### `calculate_pension_withdrawal_limit`

- 검색된 문서 근거가 있는 경우에만 실행한다.
- 필수 입력은 1 이상의 `pension_year`와 source다. 1~10년차에는 원 단위
  `account_valuation_krw`와 source가 필수이고, 11년차 이상에는 평가액 쌍을 생략할 수 있다.
- 사용자 질문 또는 검증된 검색 근거에 없는 입력을 추정하지 않는다.
- 각 입력에는 필드명, 그 값 하나와 단위가 포함된 원문 `source` 구절이 필요하다. Python은
  필드 의미, 질문 또는 검색 청크 포함 여부와 정규화 입력 일치를 검증한다. 검색 청크에서
  가져온 입력은 `chunk_id`를 계산 결과에 기록하고 최종 evidence에 자동 포함한다.
- Calculation Service의 `pension_withdrawal_limit`만 호출한다.
- 1~10년차 출력은 `withdrawal_limit`과 `limit_applies=true`다. 11년차 이상은
  `withdrawal_limit=null`, `limit_applies=false`이며 0원이나 임의의 큰 수로 표현하지 않는다.
- 호출은 한 번으로 제한한다.

### `calculate_pension_annual_limit_installment`

- 올해 남은 연금수령한도를 당해연도 잔여 지급횟수로 나누는 방식에만 사용한다.
- 입력은 `remaining_annual_limit_krw`, `remaining_payments_in_year`와 각각의 source이고,
  출력은 `installment_krw`다.
- 당해연도 잔여 지급횟수를 전체 기간 잔여회차와 혼용하지 않는다.
- 호출은 한 번으로 제한하며 다른 #116 계산 Tool과 동시에 또는 연속 실행하지 않는다.

### `calculate_pension_period_installment`

- 현재 계좌 평가액을 전체 기간 잔여회차로 나누는 방식에만 사용한다.
- 입력은 `current_valuation_krw`, `remaining_payments`와 각각의 source이고, 출력은
  `installment_krw`다.
- 다음 연도에는 당시 평가액으로 다시 산정해야 하며 Rules는 미래 평가액을 추정하지 않는다.
- 호출은 한 번으로 제한하며 다른 #116 계산 Tool과 동시에 또는 연속 실행하지 않는다.

### `calculate_pension_unit_installment`

- 잔고좌수와 1,000좌당 기준가격으로 회당 지급액을 계산하는 방식에만 사용한다.
- 입력은 `remaining_units`, `remaining_payments`,
  `standard_price_per_1000_units_krw`와 각각의 source이고, 출력은 `installment_krw`다.
- 좌수와 원화 금액을 혼용하지 않으며 호출은 한 번으로 제한한다. 다른 #116 계산 Tool과
  동시에 또는 연속 실행하지 않는다.

네 #116 Tool 모두 지급 방식 적용 여부와 검색 근거 확인은 Agent, 결정론적 산술은 Rules,
값/source의 같은 구절 대응 검증은 Tool이 담당한다. Agent와 presentation은 Python 결과를
재계산하지 않고 문서에 없는 좌수·원 단위 반올림·절사를 적용하지 않는다.

### `calculate_pension_tax_credit`

- 검색된 문서 근거가 있는 경우에만 실행한다.
- 필수 입력은 연금저축 순납입액, 퇴직연금 순납입액, 연금저축 ISA 만기자금 전환액,
  퇴직연금 ISA 만기자금 전환액(모두 원 단위)이며, 네 입력 모두 각각 값과 `source`가
  필요하다. ISA 전환이 없으면 두 전환액을 명시적 `0`으로 전달한다. 질문 또는 검색
  근거에서 ISA 전환 여부 자체를 확인할 수 없으면 이 Tool을 호출하지 않고 확정 세액을
  만들지 않는다.
- 선택 입력은 전년도 동일 만기자금 추가 공제대상액 사용분, 소득 기준
  (`income_basis`)·소득금액(`income_amount_krw`), 잔여 산출세액이며 값과 `source`가
  모두 있을 때만 함께 전달하고 하나만 있으면 호출하지 않는다. ISA 전환액이 하나라도
  0보다 크면 전년도 동일 만기자금 추가 공제대상액 사용분이 필수이고, 둘 다 0이면 이
  필드를 생략한다.
- 각 입력의 `source`는 그 금액과 같은 구절 안에서 계좌 의미(연금저축 / 퇴직연금·IRP)와
  행위 의미(순납입 / ISA 전환·만기자금 등)를 함께 포함해야 한다. 문서 전체나 다른
  구절에 흩어진 키워드와 금액만으로는 통과하지 않는다. 소득 기준의 `source`는 `총급여`
  또는 `종합소득금액` 표현을, 소득금액의 `source`는 `income_basis`와 같은 표현을
  포함해야 한다.
- 출력은 `regular_eligible_contribution_krw`, `isa_extra_remaining_cap_krw`,
  `isa_extra_limit_krw`, `isa_extra_eligible_contribution_krw`,
  `eligible_contribution_krw`이며, 소득 기준이 있으면 `credit_rate_percent`·
  `theoretical_credit_krw`(잔여 산출세액이 있으면 `usable_credit_krw` 포함)를, 없으면
  `lower_income_rate_percent`·`lower_income_theoretical_credit_krw`·
  `other_income_rate_percent`·`other_income_theoretical_credit_krw`를 함께 반환한다.
  소득 기준 없이 두 세율 시나리오만 반환되면, 모델이 제출한 상태와 무관하게 Python이
  `status=conditional`과 `총급여 또는 종합소득금액 확인 필요` 누락 조건을 강제한다.
- `usable_credit_krw`는 잔여 산출세액 기준 사용 가능한 세액이며 실제 환급액이 아니다.
- Calculation Service의 `pension_tax_credit`만 호출한다.
- 호출은 한 번으로 제한하며, `calculate_pension_withdrawal_limit`과 같은 실행에서 함께
  호출하지 않는다(질문에 맞는 계산 Tool 하나만 선택).

### `calculate_pension_income_tax`

- 세액공제를 받은 원금·운용수익의 일반 연금수령과 검증된 부득이한 사유 인출에 사용한다.
  이연퇴직소득 과세에는 사용하지 않는다.
- 필수 입력은 `pension_treatment`(`ordinary | unavoidable`)와 `recipient_age`이며 각각
  값과 원문 `source`가 필요하다. `ordinary`는 55세 이상이고 `is_lifetime_annuity` 값·
  source가 필수다. `unavoidable`은 55세 미만도 허용하지만 종신 여부와 연간 합계를 받지
  않는다.
- 현재 과세대상액, 종신 여부와 연간 사적연금 과세대상 합계는 선택 입력이며 값과 source를
  함께 전달하거나 함께 생략한다. 연간 합계는 현재 대상액을 포함한 전 금융기관의 과세대상
  사적연금소득 합계이고, 세액공제를 받지 않은 원금과 퇴직소득은 제외한다.
- 일반 연금수령에서 연간 합계가 없으면 기본세율과 `annual_threshold_status=unknown`만
  확정하고 현재 대상액이 있어도 세액을 만들지 않는다. 1,500만원 이하에서는 현재 대상액
  세액을 계산한다. 초과하면 연간 전체 합계의 16.5% 분리과세 선택세액만 계산하고 현재
  인출 세액이나 초과분 세액, 종합과세 최종세액으로 표현하지 않는다.
- 부득이한 사유 인출은 연간 1,500만원 기준을 적용하지 않으며 대상액이 있을 때만 세액을
  계산한다. 사유의 법률상 적격성은 Agent가 판단한다.
- 호출은 한 번으로 제한한다.

### `calculate_non_pension_withdrawal_tax`

- 세액공제를 받은 원금·운용수익의 연금외수령에 16.5%를 적용한다. 중도해지·일시금·
  한도초과라는 문구만으로 재원 적격성을 추론하지 않으며 이연퇴직소득에는 사용하지 않는다.
- 과세대상액은 선택 입력이다. 값과 source를 함께 생략하면 세율만, 함께 전달하면 세액과
  세후 금액을 반환한다. 둘 중 하나만 전달할 수 없다.
- 호출은 한 번으로 제한한다.
- 비교 질문에서 첫 번째 #113 계산 뒤 남은 상대 계산과 `submit_domain_result`가 같은
  모델 응답에 있으면 남은 계산만 실행하고 submit은 제거한다. 두 계산이 모두 state에
  기록된 다음 모델 턴에만 submit을 허용해 최종 결과와 결론에 두 계산을 함께 보존한다.

### `calculate_deferred_retirement_withdrawal_tax`

- 이연퇴직소득 재원의 연금수령·연금외수령 세금에만 사용하며 세액공제를 받은 원금·
  운용수익용 계산기와 혼용하지 않는다.
- 필수 입력은 `receipt_type`(`pension | non_pension`)과 원문 source다. `pension`은 실제로
  연금을 수령한 연도의 누적 횟수인 `actual_pension_receipt_year`와 source가 필수이고,
  `non_pension`에는 이 연차를 전달하지 않는다. 같은 해 여러 번 수령해도 1년이며 수령하지
  않은 연도는 누적하지 않는다. 연금수령한도용 `pension_year`와는 다른 입력이다.
- 연금수령의 실제수령 1~10년은 납부 70%·감면 30%, 11~20년은 60%·40%, 21년 이상은
  50%·50%다. 연금외수령은 납부 100%·감면 0%다.
- `allocated_deferred_retirement_tax_krw`는 선택 입력이며 계좌 전체 퇴직소득세가 아니라
  해당 인출분에 이미 배분된 이연퇴직소득세다. 값과 source가 함께 있을 때만 납부세액과
  감면세액을 반환하고 둘 다 생략되면 비율만 반환한다.
- 사용자가 납부세액·감면세액을 요구했지만 배분세액이 없으면 Agent가 `conditional`과
  `해당 인출분에 배분된 이연퇴직소득세 확인 필요` 조건을 제출한다. 단순 비율 질문은
  `determined`일 수 있으며 Python은 omission만으로 상태를 바꾸지 않는다.
- 이연퇴직소득세 원액 산출, 부분 인출분 안분, 인출 원금과 세후 인출액 계산은 범위 밖이다.
- 호출은 한 번으로 제한하며 다른 계산기와 동시에 호출하지 않는다. #113의 정확한 두 Tool
  비교 조합 예외에는 포함되지 않는다.

### `calculate_pension_withdrawal_allocation`

- 사용자가 세 재원의 인출 순서·배분만 묻거나, 요청액과 비과세·이연퇴직소득·세액공제
  원금 및 운용수익 잔액은 확인됐지만 세금 명세 조건이 부족할 때 사용한다.
- 필수 입력은 `requested_withdrawal_krw`와 세 재원 잔액 및 각 값의 `source`다. Tool은
  재원별 인출액과 남은 잔액을 반환하며 세액을 추정하지 않는다.
- 배분만 묻는 질문은 계산 결과가 완전하면 `determined`일 수 있다. allocation 결과만 있다는
  이유로 Python이 `conditional`로 바꾸지 않는다.
- 한 실행에서 아래 breakdown Tool과 둘 중 하나만, 최대 한 번 호출한다.

### `calculate_pension_withdrawal_tax_breakdown`

- 재원 배분과 재원·pension/non-pension 경로별 세액·세후액을 함께 요구하고 필요한 조건이
  모두 확인됐을 때 사용한다. 필수 입력은 allocation의 네 금액, pension/non-pension 처리액과
  각 source다. 실제 배분 경로에 따라 실제수령연차, 수령자 나이, 종신 여부, 연간 사적연금
  과세대상 합계, 해당 부분 인출분에 배분된 이연퇴직소득세와 source가 조건부 필수다.
- 계좌 전체 퇴직소득세를 부분 인출 배분세액으로 사용할 수 없다. 값과 source는 같은 의미와
  같은 금액이 포함된 구절이어야 하며 Tool이 provenance를 검증해 `input_sources`와 계산 근거
  evidence를 보존한다.
- breakdown은 내부에서 allocation과 #113·#114 Rules 순수 함수를 합성하는 단일 Calculation
  Tool이다. Agent의 Tool chaining이 아니며 먼저 allocation을 호출하지 않는다.
- 출력은 0을 포함한 여섯 경로의 인출액·세액·세후액, 현재 인출 합계 세액·세후액이며 해당할
  때 연간 전체 과세대상 사적연금소득 기준 16.5% 분리과세 선택세액을 별도로 반환한다.
  presentation은 실제 인출액이 0보다 큰 경로만 표시한다.
- Rules의 null은 그대로 전파하며 Agent나 presentation이 0으로 보완하거나 재계산·반올림하지
  않는다. 현재 인출 합계와 연간 전체 합계 기준 선택세액은 분리하고 선택세액을 현재 인출
  세액, 초과분 세액 또는 환급액으로 표현하거나 현재 인출 세액에 합산하지 않는다.
- 연간 합계 입력 없이 현재 인출 세액 또는 세후액이 null이면 모델 제출과 무관하게 Python이
  `conditional` 및 `해당 연도 사적연금 과세대상 합계 확인 필요`를 강제한다. 연간 16.5%
  선택세액이 있으면 `conditional` 및 `종합과세 또는 16.5% 분리과세 선택 필요`를 강제한다.
  기존 누락 조건은 보존하고 중복하지 않는다.
- 비과세 재원도 연금수령한도를 소진한다는 Rules warning을 보존한다. 한 실행에서 두 #115
  Tool 중 하나만 성공할 수 있고 각 Tool은 최대 한 번 호출한다. breakdown이 Rules 오류로
  실패해 `calculations`가 기록되지 않은 경우, 필요한 입력이 확인되면 allocation으로 복구할
  수 있다. 성공한 #115 계산 뒤에는 다른 계산 Tool을 차단하고 제출만 허용한다.

### `submit_domain_result`

`status="not_applicable"`은 검색 없이 바로 제출할 수 있다 — Product·Policy 책임
질문을 즉시 위임하기 위함이며, 결론·누락 조건·경고·evidence는 항상 빈 상태로
정규화된다. 그 외 상태(`determined`/`conditional`/`undetermined`)는 여전히
`search_documents`를 먼저 호출해야 하며, 모델은 판단 상태, 결론, 누락 조건, 경고와
결론에 실제 사용한 최소 청크 ID만 제출한다. 검색된 청크 전체를 그대로 제출하지
않는다. Python은 청크 ID의 UUID 형식, 중복과 SearchResult 부분집합 여부를
검증한다.

## 실행 흐름과 안전 규칙

```text
DomainRequest
  -> not_applicable ? submit_domain_result(검색 없이 즉시 정규화) : (
       search_documents 1회
       -> 검색 실패/timeout/빈 결과면 Python 안전 종료
       -> 질문과 입력에 맞는 Calculation Tool 1회
          (연금수령·연금외수령 비교만 #113 두 Tool을 각각 1회 허용)
       -> submit_domain_result(계산 없이 conclusion에 확정 수치가 있으면 비수치 재제출 1회 요청)
     )
  -> 검증된 DomainResult
```

- 검색 결과에 없는 제도, 조건과 수치를 생성하지 않는다.
- 문서에 수치가 있더라도 이를 사용자 조건에 대한 확정 계산값으로 변환하지 않는다.
- 조건·정성적 비교 질문은 확정 수치 없이 근거 기반 설명을 허용한다.
- 계산 입력의 원문 구절을 검증할 수 없으면 숫자를 생성하지 않는다.
- Tool이 지원하는 연금수령한도만 확정 계산하며 Python 결과로 결론을 교체한다.
- 지원하지 않는 계산이나 입력이 부족한 질문은 `conditional` 또는 `undetermined`로
  판단하고 필요한 입력(또는 계산 Tool 부재)을 누락 조건으로 남긴다.
- 복합 질문에서 연금수령한도만 계산되더라도 미계산 항목이 있으면 전체 상태와 누락 조건을
  보존한다.
- 근거 ID가 없으면 `not_applicable` 이외의 판단을 `undetermined`로 보정한다.
- 검색 제한사항은 `warnings`에 포함한다.
- 숫자 차단 후처리는 결론·누락 조건·경고를 필드별로 각각 검사하며, 실제 숫자·%·퍼센트·
  금액 단위가 포함된 필드만 대상으로 한다. `세율`·`한도`·`금액`·`공제액` 같은 화제어만으로는
  적용하지 않는다.
- 결론 자체에 확정 수치가 없다면 누락 조건이나 경고 중 일부에 숫자가 섞여 있어도 결론과
  상태는 그대로 두고, 숫자가 포함된 누락 조건·경고 항목만 제거한다(비수치 항목은 보존).
  이 경우 근거 없는 수치를 제거했다는 사실만 별도 경고로 남기며, 계산 Tool 필요 경고는
  추가하지 않는다. `conditional`에서 이 필터링으로 누락 조건이 하나도 안 남으면
  `결정론적 계산 Tool 결과`가 아니라 "판단에 필요한 사용자 조건"과 같은 일반 사용자
  조건 fallback을 넣는다 — 나이·가입기간 같은 일반 조건 누락을 계산 문제로 왜곡하지
  않기 위함이다.
- 결론 자체에 확정 수치가 있을 때만 `determined`/`conditional`을 계산 Tool 필요
  `conditional` 결과로 교체한다(결론·누락 조건·계산 Tool 필요 경고를 표준 문구로 통일).
- `undetermined`(근거 부족)는 숫자 차단으로 어떤 경우에도 `conditional`로 승격하지
  않는다 — "근거 부족"과 "계산 필요"는 의미가 다르다. 결론에 확정 수치가 있으면 비수치
  근거 부족 문구로만 교체하고, 기존 비수치 누락 조건은 유지한다. 비수치 누락 조건이 하나도
  남지 않을 때만 일반 근거 부족 조건을 넣는다. 계산 Tool 필요 누락 조건이나 경고는
  추가하지 않고, 근거 없는 수치를 제거했다는 별도 경고만 남긴다.
- `not_applicable` 제출은 숫자 차단 대상에서 제외한다. 결론·누락 조건·경고·evidence는
  항상 빈 상태로 정규화된다.
- 결론 자체에 확정 수치가 있으면 그 제출을 즉시 최종 결과로 확정하지 않고, 숫자 없이
  다시 제출하라는 안내와 함께 정확히 1회 재제출 기회를 준다. 재제출된 결론에 수치가
  없으면 그대로 받아들인다. 재제출도 수치를 포함하면 더 이상 기회를 주지 않고 위 숫자
  차단 후처리(표준 계산기 문구 치환 또는 `undetermined` 비수치 보정)로 확정한다. 이
  재제출 판단은 결론 필드만 대상으로 하며, 누락 조건·경고에만 숫자가 있는 경우는
  필드별 제거만 적용하고 재제출을 요구하지 않는다. 재제출 1회는 기존 `제출 Tool 최대
  2회` 한도 안에서 소비되며 별도 한도를 추가하지 않는다.

## 실행 제한

| 제한 | 값 |
|---|---:|
| 모델 호출 | 최대 5회 |
| 검색 Tool | 최대 1회 |
| 연금수령한도 Tool | 최대 1회 |
| 연금 세액공제 Tool | 최대 1회 |
| 연금수령 세금 Tool | 최대 1회 |
| 연금외수령 세금 Tool | 최대 1회 |
| 이연퇴직소득세 Tool | 최대 1회 |
| 연금 인출 재원 배분 Tool | 최대 1회 |
| 연금 인출 세금 명세 Tool | 최대 1회 |
| DB 퇴직급여 Tool | 최대 1회 |
| DC 최소 사용자 부담금 Tool | 최대 1회 |
| DC 퇴직급여 Tool | 최대 1회 |
| DB→DC 전환금액 Tool | 최대 1회 |
| 임원 퇴직소득 한도 Tool | 최대 1회 |
| 제출 Tool | 최대 2회 |
| 실행 deadline | 75초 또는 상위 deadline 중 빠른 시각 |
| 동시 실행 | 프로세스당 3개 |

## 현재 제한

- 종합과세 최종세액, 이연퇴직소득세와 과세 재원·사유의 법률상 적격성은 계산하지 않는다.
- 계산 근거 문서의 파일명·페이지 매핑은 `docs/specs/components/calculation-service.md`
  에서 관리한다(이 문서에는 중복 기록하지 않는다).
- 계산 근거 청크를 최종 결과에 제출하지 않으면 실행된 계산도 최종 `calculations`에서
  제거한다.

## 검증 위치

- `tests/unit/agent/test_domain_agents.py`
- `notebooks/agent/tax_payout_agent_playground.ipynb`

## 의료·요양 저율과세 계산

- Agent는 세법상 3개월 이상 요양과 산식 적용 사유를 판단하며 Policy의 DC 6개월 조건과 구분한다.
- 한도 질문 또는 세액 질문에서 정확한 나이가 없으면 `calculate_medical_care_withdrawal_tax_limit`, 적용 조건·원 입력·정확한 나이가 모두 확인되면 `calculate_medical_care_withdrawal_tax_breakdown`을 사용한다.
- breakdown은 Rules 내부 pure-function composite이며 limit 또는 기존 세금 Tool chaining이 아니다.
- 한 실행에서 두 #117 Tool 중 하나만 성공할 수 있고 각 Tool은 최대 1회다. 같은 model call에서는 첫 번째 #117 Tool만 유지한다.
- 성공한 #117 계산 뒤에는 submit만 허용한다. breakdown 오류로 calculation이 기록되지 않은 경우 limit fallback은 가능하다.
- #114·#115·#116 계산과 chaining하지 않으며 #117 한도는 일반 연금수령한도 및 재원 배분과 별도 의미다.
- 세액 질문에 나이가 없으면 한도를 보존하면서 `conditional`과 정확한 나이 누락 조건을 강제한다. 순수 한도 질문은 determined가 가능하다.
- breakdown 초과액의 현재 전체 세액·세후액이 null이면 Python 경계가 `conditional`과 재원·수령구분 누락 조건을 강제한다. null은 숫자로 보완하지 않는다.

## DB·DC 퇴직급여 계산

Tax/Payout Agent에는 `calculate_db_retirement_benefit`,
`calculate_dc_minimum_employer_contribution`, `calculate_dc_retirement_benefit`,
`calculate_db_to_dc_transfer_amount`을 연결하며 각 Tool은 실행당 최대 한 번 호출한다.

- DB 급여, DC 최소 사용자 부담금, DC 현재 급여와 DB→DC 전환금액의 입력 의미를 서로 바꾸지 않는다. 필수 입력과 source가 모두 확인된 경우에만 대응 Tool을 호출한다.
- 일반 #118 질문에서는 하나의 Tool만 성공할 수 있다. 명시적인 DB 퇴직급여 대 DC 퇴직급여 금액 비교에만 두 급여 Tool을 각각 한 번 허용하고, 두 계산 뒤에는 submit만 허용한다.
- 계산 성공 후 기존 세금·인출·분할지급 Tool을 자동 chaining하지 않는다. provenance 실패 시 다른 의미의 #118 Tool로 fallback하지 않는다.
- 필수 입력이 없으면 0으로 보완하지 않고 Tool을 호출하지 않는다. Python 결과 경계는 명확한 금액 요청에 구체적인 누락 조건과 `conditional`을 강제한다.
- 평균임금 제외기간, 근속 인정과 전환 가능 여부는 Policy 책임이다. Agent와 Tool은 날짜에서 포함 일수나 근속연수를 만들지 않는다.
- presentation은 Rules의 Decimal 입력·중간값·출력을 그대로 표시한다. 음의 운용손익과 음의 DC 결과를 보존하고, 전환 기준이 같으면 `두 기준 동일`로 표현한다.
- 계산 근거 문서의 filename과 locator는 이 문서에 기록하지 않는다.

## 임원 퇴직소득 한도 계산

Tax/Payout Agent에는 `calculate_executive_retirement_income_limit`을 연결하며 실행당
최대 한 번 호출한다.

- 사용자가 임원임이 질문 또는 검색 근거로 확인되고 임원 퇴직소득 한도·한도초과
  근로소득을 묻는 경우에만 호출한다. 임원 여부가 불명확하면 호출하지 않고
  `conditional`과 "임원 해당 여부 확인 필요"를 제출한다.
- DB·DC 퇴직급여 산정(#118)과 다른 소득세법상 한도 계산이며, #118 Tool 결과를 이
  Tool의 입력으로 옮기지 않는다.
- 2012~2019년, 2020년 이후 두 구간은 각각 확정된 연평균 환산 급여와 근무월수를 쌍으로
  전달하거나 둘 다 생략한다. 두 구간 중 최소 하나는 필요하며, 한 구간의 값을 다른
  구간에 복제하지 않는다.
- 근무월수는 법정 산정이 끝난 확정 월수만 사용하고 연도·재직 시작일에서 Agent가 직접
  계산하지 않는다. 날짜만 있으면 `conditional`과 해당 구간 재직월수 확인 조건을 남긴다.
- `post_2011_limit_subject_payment_krw`는 전체 퇴직금이 아니라 2012년 이후 한도
  적용대상으로 확인된 지급액이며, 이 값이 불명확하면 생략한다. 지급액 없이 구성액과
  총 한도만 요청되면 지급액을 0으로 채우지 않고 한도만 계산한다.
- 총 한도는 계산됐지만 실제 인정액·초과액을 묻는 질문에 지급액이 없으면 한도 계산
  결과는 보존하고 `conditional`과 지급액 확인 조건을 추가한다.
- 초과 근로소득은 소득 구분 금액이며 세액이 아니다. 근로소득세를 새로 계산하지 않고,
  지원하는 계산 Tool이 없으면 금액 결과를 보존한 채 세액 부분만 확인 필요로 남긴다.
- 계산 성공 후 다른 계산 Tool로 fallback하지 않고 제출만 허용한다.
- 계산 근거 문서의 filename과 locator는 이 문서에 기록하지 않는다.
