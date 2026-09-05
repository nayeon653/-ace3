# Tax/Payout calculator smoke

최종 제출 전 실제 `/answer` 경로에서 계산 Tool 호출과 입력 provenance를 확인하는
소규모 질문셋이다.

| ID | 질문 | 기대 calculator |
| --- | --- | --- |
| TAX-CALC-001 | 연금저축에 700만원 납입하고 총급여 5,000만원이면 세액공제액은? | `pension_tax_credit` |
| TAX-CALC-002 | 연금저축에 400만원, IRP에 500만원을 납입하고 총급여 7,000만원이면 세액공제 가능한 금액과 세액공제액은? | `pension_tax_credit` |
| TAX-CALC-003 | 이연퇴직소득세가 1,000만원이고 실제 연금수령 12년차라면 퇴직금을 연금으로 받을 때 세금은? | `deferred_retirement_withdrawal_tax` |
| TAX-CALC-004 | DC 가입자의 연간임금총액이 6,000만원이면 최소 사용자 부담금은? | `dc_minimum_employer_contribution` |
| TAX-CALC-005 | 올해 연금수령한도를 계산해 주세요. | `pension_withdrawal_limit` 또는 안전한 조건부 종료 |
| TAX-CALC-006 | 연금계좌 평가액이 1억원이고 연금수령 3년차이면 올해 연금수령한도는? | `pension_withdrawal_limit` |
| TAX-CALC-007 | ISA 만기일이 2026년 7월 1일이면 연금계좌 전환입금 기한과 세액공제 혜택은? | `isa_transfer_deadline` + 정적 fact |
