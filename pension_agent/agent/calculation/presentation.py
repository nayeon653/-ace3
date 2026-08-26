"""검증된 계산 결과를 사용자용 문장으로 결정론적으로 표현한다."""

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


def _value(
    outputs: dict[str, object],
    units: dict[str, str],
    key: str,
) -> str:
    value = str(outputs[key])
    unit = units.get(key)
    return f"{value} {unit}" if unit else value
