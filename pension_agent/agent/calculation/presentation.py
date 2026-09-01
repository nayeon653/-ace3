"""검증된 계산 결과를 사용자용 문장으로 결정론적으로 표현한다."""

from decimal import Decimal, InvalidOperation

from pension_agent.agent.contracts import CalculationResult


def format_calculation_summary(calculations: list[CalculationResult]) -> str:
    """등록된 계산기 결과를 값 변경 없이 한국어 요약으로 만든다."""

    lines: list[str] = []
    for calculation in calculations:
        calculator_id = calculation["calculator_id"]
        outputs = calculation["outputs"]
        units = calculation["units"]
        if calculator_id == "pension_withdrawal_limit":
            if outputs.get("limit_applies") is False:
                lines.append("연금수령 11년차 이후로 연금수령한도가 적용되지 않습니다")
            else:
                lines.append(f"연금수령한도: {_value(outputs, units, 'withdrawal_limit')}")
        elif calculator_id == "pension_annual_limit_installment":
            lines.append(
                f"당해연도 잔여한도 기준 회당 지급액: {_value(outputs, units, 'installment_krw')}"
            )
        elif calculator_id == "pension_period_installment":
            lines.append(
                "현재 평가액·전체 잔여회차 기준 회당 지급액: "
                f"{_value(outputs, units, 'installment_krw')}"
            )
        elif calculator_id == "pension_unit_installment":
            lines.append(
                "잔고좌수·1,000좌당 기준가격 기준 회당 지급액: "
                f"{_value(outputs, units, 'installment_krw')}"
            )
        elif calculator_id == "pension_tax_credit":
            lines.extend(_pension_tax_credit_lines(calculation["inputs"], outputs, units))
        elif calculator_id == "pension_income_tax":
            lines.extend(_pension_income_tax_lines(calculation["inputs"], outputs, units))
        elif calculator_id == "non_pension_withdrawal_tax":
            lines.extend(_non_pension_withdrawal_tax_lines(outputs, units))
        elif calculator_id == "deferred_retirement_withdrawal_tax":
            lines.extend(
                _deferred_retirement_withdrawal_tax_lines(calculation["inputs"], outputs, units)
            )
        elif calculator_id == "pension_withdrawal_allocation":
            lines.extend(
                _pension_withdrawal_allocation_lines(calculation["inputs"], outputs, units)
            )
        elif calculator_id == "pension_withdrawal_tax_breakdown":
            lines.extend(_pension_withdrawal_tax_breakdown_lines(outputs, units))
        elif calculator_id == "dc_medical_withdrawal_threshold":
            lines.extend(_dc_medical_withdrawal_threshold_lines(outputs, units))
        elif calculator_id == "medical_care_withdrawal_tax_limit":
            lines.extend(_medical_care_withdrawal_tax_limit_lines(outputs, units))
        elif calculator_id == "medical_care_withdrawal_tax_breakdown":
            lines.extend(_medical_care_withdrawal_tax_breakdown_lines(outputs, units))
        elif calculator_id == "db_retirement_benefit":
            lines.extend(_db_retirement_benefit_lines(calculation["inputs"], outputs, units))
        elif calculator_id == "dc_minimum_employer_contribution":
            lines.extend(_dc_minimum_employer_contribution_lines(outputs, units))
        elif calculator_id == "dc_retirement_benefit":
            lines.extend(_dc_retirement_benefit_lines(outputs, units))
        elif calculator_id == "db_to_dc_transfer_amount":
            lines.extend(_db_to_dc_transfer_amount_lines(calculation["inputs"], outputs, units))
        elif calculator_id == "executive_retirement_income_limit":
            lines.extend(
                _executive_retirement_income_limit_lines(calculation["inputs"], outputs, units)
            )
        elif calculator_id == "fund_standard_price":
            lines.append(
                "펀드 1,000좌당 기준가격: "
                f"{_value(outputs, units, 'standard_price_per_1000_units')}"
            )
        elif calculator_id == "fund_var_risk":
            lines.append(
                "연환산 97.5% VaR: "
                f"{_value(outputs, units, 'annualized_var_percent')}, "
                f"위험등급: {outputs['risk_grade']}등급 ({outputs['risk_label']})"
            )
        else:
            rendered = ", ".join(f"{key}={_value(outputs, units, key)}" for key in outputs)
            lines.append(f"{calculator_id}: {rendered}")
    return "\n".join(f"- {line}" for line in lines)


def _pension_tax_credit_lines(
    inputs: dict[str, object],
    outputs: dict[str, object],
    units: dict[str, str],
) -> list[str]:
    lines = [f"연금계좌 세액공제 대상액: {_value(outputs, units, 'eligible_contribution_krw')}"]
    if _is_positive(inputs.get("pension_savings_isa_transfer_krw")) or _is_positive(
        inputs.get("retirement_pension_isa_transfer_krw")
    ):
        lines.append(
            "ISA 추가한도: "
            f"{_value(outputs, units, 'isa_extra_limit_krw')}, "
            "ISA 추가 공제대상액: "
            f"{_value(outputs, units, 'isa_extra_eligible_contribution_krw')}, "
            "잔여 ISA 추가한도: "
            f"{_value(outputs, units, 'isa_extra_remaining_cap_krw')}"
        )
    if "credit_rate_percent" in outputs:
        lines.append(
            "적용 세액공제율: "
            f"{_value(outputs, units, 'credit_rate_percent')}, "
            "이론상 세액: "
            f"{_value(outputs, units, 'theoretical_credit_krw')}"
        )
        if "usable_credit_krw" in outputs:
            lines.append(
                f"잔여 산출세액 기준 사용 가능 세액: {_value(outputs, units, 'usable_credit_krw')}"
            )
    else:
        lines.append(
            "소득구간 미달 시(16.5%) 이론상 세액: "
            f"{_value(outputs, units, 'lower_income_theoretical_credit_krw')}, "
            "소득구간 초과 시(13.2%) 이론상 세액: "
            f"{_value(outputs, units, 'other_income_theoretical_credit_krw')}"
        )
    return lines


def _pension_income_tax_lines(
    inputs: dict[str, object],
    outputs: dict[str, object],
    units: dict[str, str],
) -> list[str]:
    treatment = inputs["pension_treatment"]
    treatment_label = "일반 연금수령" if treatment == "ordinary" else "부득이한 사유 인출"
    lines = [f"{treatment_label} 적용 기본세율: {_value(outputs, units, 'base_rate_percent')}"]
    threshold_status = outputs.get("annual_threshold_status")
    if threshold_status == "unknown":
        lines.append("연간 사적연금 과세대상 합계 미확인: 확정 세액을 계산하지 않음")
    elif threshold_status == "within":
        lines.append("연간 사적연금 과세대상 합계: 1,500만원 이하")
    elif threshold_status == "exceeded":
        lines.append("연간 사적연금 과세대상 합계: 1,500만원 초과")
        lines.append(
            "연간 전체 과세대상 사적연금소득 기준 16.5% 분리과세 선택세액: "
            f"{_value(outputs, units, 'separate_tax_option_tax_krw')}, "
            "분리과세 선택 후 금액: "
            f"{_value(outputs, units, 'separate_tax_option_after_tax_krw')}"
        )
    if "tax_krw" in outputs:
        lines.append(
            f"과세대상액 세액: {_value(outputs, units, 'tax_krw')}, "
            f"세후 금액: {_value(outputs, units, 'after_tax_krw')}"
        )
    return lines


def _non_pension_withdrawal_tax_lines(
    outputs: dict[str, object],
    units: dict[str, str],
) -> list[str]:
    lines = [
        (
            "세액공제 원금·운용수익의 연금외수령 적용 기본세율: "
            f"{_value(outputs, units, 'base_rate_percent')}"
        )
    ]
    if "tax_krw" in outputs:
        lines.append(
            f"연금외수령 과세대상액 세액: {_value(outputs, units, 'tax_krw')}, "
            f"세후 금액: {_value(outputs, units, 'after_tax_krw')}"
        )
    return lines


def _deferred_retirement_withdrawal_tax_lines(
    inputs: dict[str, object],
    outputs: dict[str, object],
    units: dict[str, str],
) -> list[str]:
    receipt_label = "연금수령" if inputs["receipt_type"] == "pension" else "연금외수령"
    lines = [
        (
            f"이연퇴직소득 {receipt_label} 납부 비율: "
            f"{_value(outputs, units, 'payable_ratio_percent')}, "
            f"감면 비율: {_value(outputs, units, 'reduction_ratio_percent')}"
        )
    ]
    if "tax_payable_krw" in outputs:
        lines.append(
            "해당 인출분에 배분된 이연퇴직소득세 기준 납부세액: "
            f"{_value(outputs, units, 'tax_payable_krw')}"
        )
    if "tax_reduction_krw" in outputs:
        lines.append(
            "해당 인출분에 배분된 이연퇴직소득세 기준 감면세액: "
            f"{_value(outputs, units, 'tax_reduction_krw')}"
        )
    return lines


def _pension_withdrawal_allocation_lines(
    inputs: dict[str, object],
    outputs: dict[str, object],
    units: dict[str, str],
) -> list[str]:
    return [
        f"요청 인출액: {_value(inputs, units, 'requested_withdrawal_krw')}",
        (
            "비과세 재원 인출액: "
            f"{_value(outputs, units, 'tax_free_withdrawal_krw')}, 남은 잔액: "
            f"{_value(outputs, units, 'tax_free_remaining_balance_krw')}"
        ),
        (
            "이연퇴직소득 인출액: "
            f"{_value(outputs, units, 'deferred_retirement_withdrawal_krw')}, 남은 잔액: "
            f"{_value(outputs, units, 'deferred_retirement_remaining_balance_krw')}"
        ),
        (
            "세액공제 원금·운용수익 인출액: "
            f"{_value(outputs, units, 'credited_and_earnings_withdrawal_krw')}, 남은 잔액: "
            f"{_value(outputs, units, 'credited_and_earnings_remaining_balance_krw')}"
        ),
    ]


def _pension_withdrawal_tax_breakdown_lines(
    outputs: dict[str, object],
    units: dict[str, str],
) -> list[str]:
    labels = {
        "tax_free_pension": "비과세 재원·연금 처리",
        "tax_free_non_pension": "비과세 재원·연금외 처리",
        "deferred_retirement_pension": "이연퇴직소득·연금 처리",
        "deferred_retirement_non_pension": "이연퇴직소득·연금외 처리",
        "credited_and_earnings_pension": "세액공제 원금·운용수익·연금 처리",
        "credited_and_earnings_non_pension": "세액공제 원금·운용수익·연금외 처리",
    }
    lines: list[str] = []
    for path, label in labels.items():
        withdrawal_key = f"{path}_withdrawal_krw"
        if not _is_positive(outputs.get(withdrawal_key)):
            continue
        tax_key = f"{path}_tax_krw"
        after_tax_key = f"{path}_after_tax_krw"
        lines.append(
            f"{label} 인출액: {_value(outputs, units, withdrawal_key)}, "
            f"세액: {_value_or_unresolved(outputs, units, tax_key)}, "
            f"세후액: {_value_or_unresolved(outputs, units, after_tax_key)}"
        )
    if (
        outputs.get("current_withdrawal_tax_krw") is None
        or outputs.get("current_withdrawal_after_tax_krw") is None
    ):
        lines.append("현재 인출 합계 세액·세후액: 확정할 수 없음")
    else:
        lines.append(
            "현재 인출 합계 세액: "
            f"{_value(outputs, units, 'current_withdrawal_tax_krw')}, 세후액: "
            f"{_value(outputs, units, 'current_withdrawal_after_tax_krw')}"
        )
    if outputs.get("annual_private_pension_separate_tax_option_tax_krw") is not None:
        lines.append(
            "연간 전체 과세대상 사적연금소득 기준 16.5% 분리과세 선택세액: "
            f"{_value(outputs, units, 'annual_private_pension_separate_tax_option_tax_krw')}"
        )
    return lines


def _dc_medical_withdrawal_threshold_lines(
    outputs: dict[str, object], units: dict[str, str]
) -> list[str]:
    basis_labels = {
        "previous_year_annual_wages": "직전연도 연간임금총액",
        "preceding_12_month_wages": "신청일 기준 직전 12개월 임금",
        "annualized_average_monthly_wage": "재직 중 월평균 급여의 연환산액",
    }
    basis = basis_labels.get(str(outputs["wage_basis"]), str(outputs["wage_basis"]))
    met = "충족" if outputs["threshold_met"] is True else "미충족"
    return [
        f"DC 의료비 기준 적용 임금: {basis}",
        f"적용 임금 기준액: {_value(outputs, units, 'applicable_wages_krw')}",
        f"임금 기준액의 12.5%: {_value(outputs, units, 'medical_expense_threshold_krw')}",
        f"증빙 의료비의 12.5% 기준 엄격 초과 여부: {met}",
    ]


def _medical_care_withdrawal_tax_limit_lines(
    outputs: dict[str, object], units: dict[str, str]
) -> list[str]:
    return [
        f"의료·요양 저율과세 한도: {_value(outputs, units, 'tax_limit_krw')}",
        f"한도 내 금액: {_value(outputs, units, 'amount_within_limit_krw')}",
        f"초과액: {_value(outputs, units, 'excess_amount_krw')}",
    ]


def _medical_care_withdrawal_tax_breakdown_lines(
    outputs: dict[str, object], units: dict[str, str]
) -> list[str]:
    return [
        f"의료·요양 저율과세 한도: {_value(outputs, units, 'tax_limit_krw')}",
        f"한도 내 금액: {_value(outputs, units, 'amount_within_limit_krw')}",
        f"한도 내 세율: {_value(outputs, units, 'within_limit_tax_rate_percent')}",
        f"한도 내 세액: {_value(outputs, units, 'within_limit_tax_krw')}",
        f"한도 내 세후액: {_value(outputs, units, 'within_limit_after_tax_krw')}",
        f"초과액: {_value(outputs, units, 'excess_amount_krw')}",
        f"현재 전체 세액: {_value_or_unresolved(outputs, units, 'current_withdrawal_tax_krw')}",
        (
            "현재 전체 세후액: "
            f"{_value_or_unresolved(outputs, units, 'current_withdrawal_after_tax_krw')}"
        ),
    ]


def _db_retirement_benefit_lines(
    inputs: dict[str, object], outputs: dict[str, object], units: dict[str, str]
) -> list[str]:
    return [
        (
            "평균임금 산정 대상 최근 3개월 임금 합계: "
            f"{_value(inputs, {'wages_for_average_period_krw': 'KRW'}, 'wages_for_average_period_krw')}"
        ),
        f"평균임금 산정 포함 일수: {inputs['included_days_for_average_wage']}일",
        f"평균일급: {_value(outputs, units, 'average_daily_wage')}",
        f"30일 평균임금: {_value(outputs, units, 'average_wage_30_days')}",
        f"검증된 계속근로연수: {_value(outputs, units, 'verified_service_years')}",
        f"DB 퇴직급여: {_value(outputs, units, 'retirement_benefit')}",
    ]


def _dc_minimum_employer_contribution_lines(
    outputs: dict[str, object], units: dict[str, str]
) -> list[str]:
    return [
        f"연간임금총액: {_value(outputs, units, 'annual_total_wages')}",
        f"DC 최소 사용자 부담금: {_value(outputs, units, 'minimum_employer_contribution')}",
    ]


def _dc_retirement_benefit_lines(outputs: dict[str, object], units: dict[str, str]) -> list[str]:
    return [
        f"DC 실제 누적 부담금: {_value(outputs, units, 'accumulated_contributions')}",
        f"누적 운용손익: {_value(outputs, units, 'investment_gain_loss')}",
        f"DC 퇴직급여: {_value(outputs, units, 'retirement_benefit')}",
    ]


def _db_to_dc_transfer_amount_lines(
    inputs: dict[str, object], outputs: dict[str, object], units: dict[str, str]
) -> list[str]:
    basis_labels = {
        "average_wage_30_days": "최종 30일 평균임금",
        "annual_wage_monthly_basis": "최종 연간임금총액의 월 기준값",
        "equal": "두 기준 동일",
    }
    basis_type = str(outputs["selected_basis_type"])
    return [
        f"전환 기준 최종 30일 평균임금: {_value(outputs, units, 'final_average_wage_30_days')}",
        (
            "전환 기준 최종 연간임금총액: "
            f"{_value(inputs, {'final_annual_total_wages_krw': 'KRW'}, 'final_annual_total_wages_krw')}"
        ),
        f"최종 연간임금의 월 기준값: {_value(outputs, units, 'annual_wage_monthly_basis')}",
        (
            f"선택된 전환 기준: {basis_labels.get(basis_type, basis_type)}, "
            f"{_value(outputs, units, 'selected_basis')}"
        ),
        f"검증된 근속연수: {_value(outputs, units, 'verified_service_years')}",
        f"DB→DC 전환금액: {_value(outputs, units, 'transfer_amount')}",
    ]


def _executive_retirement_income_limit_lines(
    inputs: dict[str, object], outputs: dict[str, object], units: dict[str, str]
) -> list[str]:
    lines = [
        f"2012~2019년 한도 구성액: {_value(outputs, units, 'limit_2012_2019_krw')}",
        f"2020년 이후 한도 구성액: {_value(outputs, units, 'limit_2020_onward_krw')}",
        f"임원 퇴직소득 한도 합계: {_value(outputs, units, 'post_2011_total_limit_krw')}",
    ]
    if "retirement_income_amount_krw" in outputs:
        lines.append(
            "2012년 이후 한도 적용대상 퇴직급여: "
            f"{_value(inputs, {'post_2011_limit_subject_payment_krw': 'KRW'}, 'post_2011_limit_subject_payment_krw')}"
        )
        lines.append(f"퇴직소득 인정액: {_value(outputs, units, 'retirement_income_amount_krw')}")
        lines.append(f"한도 초과 근로소득 금액: {_value(outputs, units, 'wage_income_excess_krw')}")
    return lines


def _is_positive(value: object) -> bool:
    if value is None:
        return False
    try:
        return Decimal(str(value)) > 0
    except InvalidOperation:
        return False


def _value(
    outputs: dict[str, object],
    units: dict[str, str],
    key: str,
) -> str:
    value = str(outputs[key])
    unit = units.get(key)
    return f"{value} {unit}" if unit else value


def _value_or_unresolved(
    outputs: dict[str, object],
    units: dict[str, str],
    key: str,
) -> str:
    return "확정할 수 없음" if outputs.get(key) is None else _value(outputs, units, key)
