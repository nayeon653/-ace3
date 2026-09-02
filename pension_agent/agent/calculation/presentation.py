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
            lines.append(f"연금수령한도: {_value(outputs, units, 'withdrawal_limit')}")
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
